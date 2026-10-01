"""Admission problem: offer or defer each ride request of a ride-hailing operator.

- Features: the fleet state, the pending search, the fleet yield and the time of day.
- Action: offer the alternatives or defer the request.
- Reward: ``Profit``, the profit of the period, or ``Surplus``, the surplus of the decision.

The surplus of a decision:

- An offer earns the fare of the nearest alternative minus its distance cost and vehicle time.
- A deferral costs one waiting minute of the user.

The surplus rewards do not sum to the profit of the episode.
Evaluate a policy trained on them with the profit reward.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import numpy as np
from gymnasium.spaces import Discrete
from numpy.typing import NDArray

from rl.adapters import BrokeredAdmissionSearchEngine, Search
from rl.operator_problem import OperatorProblem
from rl.problems.features import (
    CLOCK_FEATURES,
    STATE_FEATURES,
    box,
    clock,
    squash,
    state_shares,
)
from simulation.helper.configuration.configuration import RideHailingOperationsConfig
from simulation.operator.accounting import CostType

if TYPE_CHECKING:
    from gymnasium.spaces import Box

    from rl.bookkeeper import SettlementPeriod
    from rl.channel import DecisionRequest
    from rl.problem import Period
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.simulation import Simulation

DEFER = 0
"""Action that answers the search with no alternatives."""

OFFER = 1
"""Action that offers the alternatives as found."""

_FARE_SCALE = 10.0
"""Fare at which the ``fare`` entry reads one half."""

_SEARCHED_SCALE_MIN = 5.0
"""Minutes of searching at which the ``searched`` entry reads one half."""

_YIELD_SPAN_MIN = 60.0
"""Minutes after which a settled period leaves the fleet yield."""

_YIELD_SCALE_PER_MIN = 0.25
"""Yield (per vehicle-minute) at which the ``yield`` entry reads one half."""

_METRES_PER_KM = 1000.0

SEARCH_FEATURES = ("candidates", "pickup", "trip", "fare", "searched")
"""Entries that describe the pending search, zero at the horizon."""

FEATURES = (*STATE_FEATURES, *SEARCH_FEATURES, "yield", *CLOCK_FEATURES)
"""Observation entries in order.

The first six entries are the share of the fleet in each vehicle state, ``standby`` to ``offline``.
Every trip state counts as ``transporting``. The six shares sum to one.

The next five entries describe the pending search and are zero at the horizon:

- ``candidates`` is the share of the fleet the search found for the request.
- ``pickup`` is the shortest pickup leg among the found alternatives, as a share of the pickup radius.
- ``trip`` is the trip distance of the alternative with that pickup leg.
- ``fare`` is the fare of the same alternative.
- ``searched`` is the number of minutes the user has been searching.

``yield`` is the net fares per vehicle-minute of the fleet over the settled periods that ended within the last hour.
``clock_sin`` and ``clock_cos`` are the sine and cosine of the time of day.

``trip``, ``fare``, ``searched`` and ``yield`` have no upper bound, so ``squash`` maps them into 0 to 1.

``candidates`` overstates supply at a peak:
Vehicles are reserved only in the allocation batch one minute later.
Several searches at one instant can therefore be offered the same vehicle.
"""


@dataclass(frozen=True, slots=True)
class Admission:
    """
    One answered search, what a ``Reward`` prices.

    Attributes
    ----------
    nearest : TransportationAlternative
        Found alternative with the shortest pickup leg.
    is_offered : bool
        Whether the alternatives were offered or the request deferred.
    fleet_yield : float
        Yield per vehicle-minute the decision saw.
    """

    nearest: TransportationAlternative
    is_offered: bool
    fleet_yield: float


@runtime_checkable
class Reward(Protocol):
    """Protocol of the reward an ``AdmissionProblem`` pays each step."""

    def of(self, settlement: SettlementPeriod, admission: Admission) -> float:
        """Return the reward for the settlement of the period that just closed and the admission the step answered.

        Parameters
        ----------
        settlement : SettlementPeriod
            Revenue, cost and log entries of the closed period.
        admission : Admission
            Search the action answered, with the yield the decision saw.
        """
        ...


@dataclass(frozen=True, slots=True)
class Profit:
    """
    Reward paying each step the profit of its settlement period.

    These rewards sum to the profit of the episode after the first decision point.
    """

    def of(self, settlement: SettlementPeriod, admission: Admission) -> float:
        """Return the profit of the settlement, the admission unused."""
        return settlement.profit


@dataclass(frozen=True, slots=True)
class Surplus:
    """
    Reward paying each decision its own estimated consequence, see ``of``.

    Useful for training, but the profit reward is the one to evaluate a policy with.

    Parameters
    ----------
    wait_cost_per_min : float
        Cost of one waiting minute of a deferred user. Zero prices service at nothing.

    Raises
    ------
    ValueError
        If ``wait_cost_per_min`` is negative.
    """

    wait_cost_per_min: float = 0.0

    def __post_init__(self) -> None:
        """Reject a negative waiting cost."""
        if self.wait_cost_per_min < 0:
            msg = f"Expected a waiting cost of zero or more, got {self.wait_cost_per_min}."
            raise ValueError(msg)

    def of(self, settlement: SettlementPeriod, admission: Admission) -> float:
        """Return the surplus of the admission, the settlement unused.

        An offer pays the fare of the nearest alternative minus its costs:

        - The distance cost of the pickup leg and the trip.
        - The vehicle-minutes of both, priced at the yield the decision saw.

        A deferral pays minus ``wait_cost_per_min``, for the minute the user waits before the next search.
        """
        if not admission.is_offered:
            return -self.wait_cost_per_min
        nearest = admission.nearest
        pickup_m = _pickup_distance(nearest)
        vehicle = nearest.vehicle
        minutes = vehicle.calculate_travel_time(pickup_m) + nearest.duration
        distance_km = (pickup_m + nearest.distance) / _METRES_PER_KM
        distance_cost = vehicle.cost_config.PER_KM * distance_km
        return nearest.price - distance_cost - admission.fleet_yield * minutes


@dataclass(frozen=True, slots=True)
class _Settled:
    """The span and the net fares of one settled period."""

    start_min: float
    end_min: float
    net_fares: float


class _FleetYield:
    """The net fares per vehicle-minute over the settled periods that ended within the last hour."""

    __slots__ = ("_fleet_size", "_net_fares", "_settled")

    def __init__(self, fleet_size: int) -> None:
        self._fleet_size = fleet_size
        self._settled: deque[_Settled] = deque()
        self._net_fares = 0.0

    @property
    def value(self) -> float:
        """Return the net fares per vehicle-minute over the retained periods, never below zero."""
        if not self._settled:
            return 0.0
        span_min = self._settled[-1].end_min - self._settled[0].start_min
        if span_min <= 0:
            return 0.0
        return max(self._net_fares / (self._fleet_size * span_min), 0.0)

    def record(self, period: SettlementPeriod) -> None:
        """Add the period to the span and drop the periods that fell out of it."""
        net_fares = period.revenue - period.costs_by_type[CostType.VEHICLE_DISTANCE]
        self._settled.append(_Settled(period.start_min, period.end_min, net_fares))
        self._net_fares += net_fares
        cutoff_min = period.end_min - _YIELD_SPAN_MIN
        while self._settled and self._settled[0].end_min <= cutoff_min:
            self._net_fares -= self._settled.popleft().net_fares


@dataclass(slots=True)
class _Episode:
    """
    Per-episode state of an ``AdmissionProblem``, built when the episode starts.

    Attributes
    ----------
    radius_m : float
        Pickup radius of the operator (m).
    fleet_yield : _FleetYield
        Yield over the settled periods of the last hour.
    offered : int
        Searches offered so far.
    deferred : int
        Searches deferred so far.
    admission : Admission or None
        Last search answered, what the reward prices. None before the first.
    """

    radius_m: float
    fleet_yield: _FleetYield
    offered: int = 0
    deferred: int = 0
    admission: Admission | None = None


class AdmissionProblem(OperatorProblem[NDArray[np.float32], np.int64]):
    """
    An OperatorProblem that offers or defers each ride request of a ride-hailing operator.

    The operator must have ``BrokeredAdmissionSearchEngine`` as its search engine.

    Parameters
    ----------
    reward : Reward
        Reward of each step, ``Profit`` of its period or ``Surplus`` of its decision.

    Raises
    ------
    TypeError
        If ``reward`` is a class or has no ``of`` method, such as the string ``"surplus"``.
    """

    def __init__(self, reward: Reward = Profit()) -> None:
        if isinstance(reward, type) or not isinstance(reward, Reward):
            msg = f"Expected a Reward such as Profit() or Surplus(), got {reward!r}."
            raise TypeError(msg)
        super().__init__()
        self._reward = reward
        self._episode: _Episode | None = None

    @property
    def fleet_yield(self) -> float:
        """Return the net fares per vehicle-minute over the periods that ended within the last hour, never below zero."""
        return self._current.fleet_yield.value

    @property
    def observation_space(self) -> Box:
        """Return the flat ``Box`` in ``FEATURES`` order, clock entries in -1 to 1 and the rest in 0 to 1."""
        return box(FEATURES, signed_entries=CLOCK_FEATURES)

    @property
    def action_space(self) -> Discrete:
        """Return the space of the two actions, ``DEFER`` and ``OFFER``."""
        return Discrete(2)

    def on_episode_start(self, simulation: Simulation) -> None:
        """Pick the operator, check its search engine, operations and fleet, then start a fresh episode state.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode, built but not yet run.

        Raises
        ------
        TypeError
            If the search engine is not ``BrokeredAdmissionSearchEngine`` or the
            operations are not ride-hailing ones.
        ValueError
            If the world has no single operator or the operator has no vehicles.
        """
        super().on_episode_start(simulation)
        search_engine = self.operator.search_engine
        if not isinstance(search_engine, BrokeredAdmissionSearchEngine):
            msg = (
                f"{type(search_engine).__name__} is not a "
                "BrokeredAdmissionSearchEngine. Configure a search engine that is."
            )
            raise TypeError(msg)
        config = self.operator.operations.config
        if not isinstance(config, RideHailingOperationsConfig):
            msg = (
                f"{type(config).__name__} is not a RideHailingOperationsConfig, so "
                "it has no pickup radius. Configure ride-hailing operations."
            )
            raise TypeError(msg)
        fleet_size = len(self.operator.fleet.vehicles)
        if fleet_size == 0:
            msg = "AdmissionProblem needs an operator with at least one vehicle."
            raise ValueError(msg)
        self._episode = _Episode(
            radius_m=float(config.MAX_PICKUP_DISTANCE),
            fleet_yield=_FleetYield(fleet_size),
        )

    def close_period(self, simulation: Simulation, period: Period) -> None:
        """Settle the period and add its settlement to the yield span.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period, from the previous decision point or from episode start.
        """
        super().close_period(simulation, period)
        self._current.fleet_yield.record(self.settlement)

    def build_observation(
        self, simulation: Simulation, period: Period, request: DecisionRequest | None
    ) -> NDArray[np.float32]:
        """Return the fleet state, the yield, the pending search and the time of day.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period, unused.
        request : DecisionRequest or None
            Pending decision, carrying a ``Search``. None at the horizon.

        Returns
        -------
        numpy.ndarray
            Entries in ``FEATURES`` order.

        Raises
        ------
        TypeError
            If the decision carries no ``Search`` payload.
        """
        vehicles = self.operator.fleet.vehicles
        now_min = simulation.sim.time
        search = None if request is None else _search(request)
        entries = {
            **state_shares(vehicles),
            **self._search_entries(now_min, len(vehicles), search),
            "yield": squash(self.fleet_yield, _YIELD_SCALE_PER_MIN),
            **clock(now_min),
        }
        return np.array([entries[name] for name in FEATURES], dtype=np.float32)

    def apply_action(
        self, simulation: Simulation, request: DecisionRequest, action: np.int64
    ) -> bool:
        """Return the reply to the waiting search: True for ``OFFER``, False for ``DEFER``.

        Records the admission with the yield it sees, which ``compute_reward`` prices.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        request : DecisionRequest
            Decision the action answers, carrying the ``Search``.
        action : numpy.int64
            ``DEFER`` or ``OFFER``.

        Returns
        -------
        bool
            Reply for the waiting search. True offers the alternatives.

        Raises
        ------
        TypeError
            If the decision carries no ``Search`` payload.
        ValueError
            If the action is neither ``DEFER`` nor ``OFFER``.
        """
        value = np.asarray(action).item()
        if value not in (DEFER, OFFER):
            msg = f"Expected {DEFER} to defer or {OFFER} to offer, got {value!r}."
            raise ValueError(msg)
        nearest = _nearest(_search(request))
        episode = self._current
        is_offered = value == OFFER
        episode.admission = Admission(nearest, is_offered, self.fleet_yield)
        if is_offered:
            episode.offered += 1
        else:
            episode.deferred += 1
        return is_offered

    def compute_reward(self, simulation: Simulation, period: Period) -> float:
        """Return what the reward pays for the settlement of the period and the admission the step answered.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period, the bounds of ``settlement``.

        Raises
        ------
        RuntimeError
            If no search was answered yet, so ``apply_action`` did not run.
        """
        admission = self._current.admission
        if admission is None:
            msg = (
                "compute_reward() needs an answered search. Call apply_action() first."
            )
            raise RuntimeError(msg)
        return self._reward.of(self.settlement, admission)

    def info(self, simulation: Simulation, period: Period) -> dict[str, Any]:
        """Return the settlement of the period and the counts of offered and deferred searches in this episode.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period, the bounds of ``settlement``.
        """
        episode = self._current
        return {
            **super().info(simulation, period),
            "offered": episode.offered,
            "deferred": episode.deferred,
        }

    @property
    def _current(self) -> _Episode:
        """Return the state of the running episode, or raise before one starts."""
        if self._episode is None:
            msg = "No episode runs. Call reset() first."
            raise RuntimeError(msg)
        return self._episode

    def _search_entries(
        self, now_min: float, fleet_size: int, search: Search | None
    ) -> dict[str, float]:
        """Return the entries in ``SEARCH_FEATURES``, all zero at the horizon."""
        if search is None:
            return dict.fromkeys(SEARCH_FEATURES, 0.0)
        radius_m = self._current.radius_m
        nearest = _nearest(search)
        searched_min = max(now_min - search.transport_request.creation_time, 0.0)
        return {
            "candidates": min(len(search.alternatives) / fleet_size, 1.0),
            "pickup": min(_pickup_distance(nearest) / radius_m, 1.0),
            "trip": squash(nearest.distance, radius_m),
            "fare": squash(nearest.price, _FARE_SCALE),
            "searched": squash(searched_min, _SEARCHED_SCALE_MIN),
        }


def _search(request: DecisionRequest) -> Search:
    """Return the ``Search`` the decision carries.

    Raises
    ------
    TypeError
        If the payload is no ``Search``, so the decision came from another seam.
    """
    payload = request.payload
    if not isinstance(payload, Search):
        msg = (
            f"Expected a Search as the decision payload, got {type(payload).__name__}."
        )
        raise TypeError(msg)
    return payload


def _nearest(search: Search) -> TransportationAlternative:
    """Return the found alternative with the shortest pickup leg."""
    return min(search.alternatives, key=_pickup_distance)


def _pickup_distance(alternative: TransportationAlternative) -> float:
    """Return the pickup leg of the alternative (m).

    Raises
    ------
    ValueError
        If the alternative has no route to pickup. The ride-hailing search sets one on every alternative.
    """
    route = alternative.route_to_pickup
    if route is None:
        msg = "Expected a route to pickup on every alternative the search found, got None."
        raise ValueError(msg)
    return route.distance
