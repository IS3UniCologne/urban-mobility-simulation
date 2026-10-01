"""Tests for AdmissionProblem, on fakes and on a real simulation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import numpy as np
import pytest

pytest.importorskip("gymnasium")
pytest.importorskip("greenlet")

from gymnasium.utils.env_checker import check_env

from rl.adapters import BrokeredAdmissionSearchEngine, Search
from rl.channel import DecisionRequest
from rl.problem import Period
from rl.problems import AdmissionProblem
from rl.problems.admission import DEFER, FEATURES, OFFER, SEARCH_FEATURES, Surplus
from simulation.helper.configuration.configuration import RideHailingOperationsConfig
from simulation.helper.types import SimId
from simulation.helper.vehicle_states import VehicleStates
from simulation.operator.accounting import CostType
from tests.rl.fakes import OPERATOR_ID, FakeVehicle, make_simulation, operator_of

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from rl.env import UmosimEnv

RADIUS_M = 10000.0
PER_KM = 0.5
METRES_PER_MIN = 100.0
PERIOD = Period(0.0, 15.0)


def make_request(
    payload: object = None, requester_id: SimId = OPERATOR_ID
) -> DecisionRequest:
    """Build a pending decision, of the fake operator unless another requester is given."""
    return DecisionRequest(requester_id=requester_id, payload=payload)


def make_search(
    alternatives: list[tuple[float, float, float]], created_at: float = 0.0
) -> Search:
    """Build a search payload, one alternative per (pickup leg m, trip m, fare).

    Every vehicle drives ``METRES_PER_MIN`` and costs ``PER_KM``.
    """
    vehicle = FakeVehicle(
        "Vehicle_0", cost_per_km=PER_KM, metres_per_min=METRES_PER_MIN
    )
    return Search(
        transport_request=SimpleNamespace(creation_time=created_at),  # type: ignore[arg-type]
        alternatives=tuple(
            SimpleNamespace(
                vehicle=vehicle,
                route_to_pickup=SimpleNamespace(distance=pickup_m),
                distance=trip_m,
                duration=trip_m / METRES_PER_MIN,
                price=fare,
            )
            for pickup_m, trip_m, fare in alternatives
        ),  # type: ignore[arg-type]
    )


def wire(simulation: SimpleNamespace) -> None:
    """Give a fake simulation's operator the adapter and ride-hailing operations."""
    operator = operator_of(simulation)
    operator.search_engine = Mock(spec=BrokeredAdmissionSearchEngine)
    config = Mock(spec=RideHailingOperationsConfig)
    config.MAX_PICKUP_DISTANCE = RADIUS_M
    operator.operations.config = config


def start_episode(
    vehicles: list[FakeVehicle],
    now: float = 0.0,
    problem: AdmissionProblem | None = None,
) -> tuple[AdmissionProblem, SimpleNamespace]:
    """Start a problem, the profit reward by default, on a wired fake simulation and return both."""
    simulation = make_simulation(vehicles, now=now)
    wire(simulation)
    if problem is None:
        problem = AdmissionProblem()
    problem.on_episode_start(simulation)
    return problem, simulation


def decide(
    problem: AdmissionProblem,
    simulation: SimpleNamespace,
    search: Search,
    action: object,
) -> bool:
    """Hand the problem a decision carrying ``search`` and answer it with ``action``."""
    request = make_request(search)
    problem.on_request(simulation, request)
    return problem.apply_action(simulation, request, action)  # type: ignore[arg-type]


def settle(
    problem: AdmissionProblem,
    simulation: SimpleNamespace,
    start_min: float,
    end_min: float,
    revenue: float = 0.0,
    costs: dict[CostType, float] | None = None,
) -> None:
    """Book ``revenue`` and ``costs`` on the fake ledger, then close the period."""
    ledger = operator_of(simulation).ledger
    ledger.revenue_total += revenue
    for cost_type, amount in (costs or {}).items():
        ledger.costs[cost_type] += amount
    problem.close_period(simulation, Period(start_min, end_min))


@pytest.mark.unit
def test_observation_describes_the_fleet_and_the_pending_search() -> None:
    """State shares, the nearest alternative's legs and fare, the search time and the clock."""
    problem, simulation = start_episode(
        [
            FakeVehicle("Vehicle_1", VehicleStates.STANDBY),
            FakeVehicle("Vehicle_2", VehicleStates.DRIVING),
            FakeVehicle("Vehicle_3", VehicleStates.WAITING_FOR_CHARGING),
            FakeVehicle("Vehicle_4", VehicleStates.CHARGING),
        ],
        now=360.0,
    )
    search = make_search(
        [(4000.0, 8000.0, 20.0), (2000.0, 10000.0, 10.0)], created_at=357.0
    )

    observation = problem.build_observation(simulation, PERIOD, make_request(search))

    expected = {
        "standby": 0.25,
        "transporting": 0.25,
        "relocating": 0.0,
        "waiting_for_charging": 0.25,
        "charging": 0.25,
        "offline": 0.0,
        "candidates": 0.5,
        "pickup": 0.2,
        "trip": 0.5,
        "fare": 0.5,
        "searched": 3 / 8,
        "yield": 0.0,
        "clock_sin": 1.0,
        "clock_cos": 0.0,
    }
    assert observation in problem.observation_space
    np.testing.assert_allclose(
        observation, [expected[name] for name in FEATURES], atol=1e-6
    )


@pytest.mark.unit
def test_observation_at_the_horizon_carries_no_search() -> None:
    """With nothing pending the five search entries are zero."""
    problem, simulation = start_episode([FakeVehicle("Vehicle_1")])

    observation = problem.build_observation(simulation, PERIOD, None)

    assert [observation[FEATURES.index(name)] for name in SEARCH_FEATURES] == [0.0] * 5
    assert observation in problem.observation_space


@pytest.mark.unit
def test_yield_averages_the_last_hours_net_fares_per_vehicle_minute() -> None:
    """Fares net of distance cost over the periods of the last hour, per vehicle-minute of the span they cover."""
    problem, simulation = start_episode(
        [FakeVehicle("Vehicle_1"), FakeVehicle("Vehicle_2")]
    )

    settle(
        problem,
        simulation,
        0.0,
        30.0,
        revenue=60.0,
        costs={CostType.VEHICLE_DISTANCE: 12.0},
    )
    settle(problem, simulation, 30.0, 50.0, revenue=24.0)
    within_the_hour = problem.fleet_yield
    settle(problem, simulation, 50.0, 100.0)
    observation = problem.build_observation(simulation, Period(50.0, 100.0), None)

    assert within_the_hour == pytest.approx(72.0 / (2 * 50))
    assert problem.fleet_yield == pytest.approx(24.0 / (2 * 70))
    assert observation[FEATURES.index("yield")] == pytest.approx(
        (24.0 / 140) / (24.0 / 140 + 0.25)
    )


@pytest.mark.unit
def test_yield_does_not_depend_on_the_settlement_cadence() -> None:
    """Uniform earnings report the same yield settled as one long period or as three short ones.

    The first of the three short periods leaves the hour, the other two are summed.
    """
    long_period, long_simulation = start_episode([FakeVehicle("Vehicle_1")])
    short_periods, short_simulation = start_episode([FakeVehicle("Vehicle_1")])

    settle(long_period, long_simulation, 0.0, 120.0, revenue=120.0)
    for start in (0.0, 40.0, 80.0):
        settle(short_periods, short_simulation, start, start + 40.0, revenue=40.0)

    assert long_period.fleet_yield == pytest.approx(1.0)
    assert short_periods.fleet_yield == pytest.approx(1.0)


@pytest.mark.unit
def test_surplus_reward_is_the_offered_assignments_surplus() -> None:
    """Fare net of distance cost and of vehicle time at the yield the decision saw, whatever the period earned."""
    problem, simulation = start_episode(
        [FakeVehicle("Vehicle_1"), FakeVehicle("Vehicle_2")],
        problem=AdmissionProblem(Surplus()),
    )
    settle(problem, simulation, 0.0, 10.0, revenue=20.0)
    search = make_search([(4000.0, 8000.0, 30.0), (2000.0, 10000.0, 20.0)])

    decide(problem, simulation, search, OFFER)
    settle(problem, simulation, 10.0, 11.0, revenue=999.0)
    offered = problem.compute_reward(simulation, Period(10.0, 11.0))
    decide(problem, simulation, search, DEFER)
    settle(problem, simulation, 11.0, 12.0)
    deferred = problem.compute_reward(simulation, Period(11.0, 12.0))

    assert offered == pytest.approx(20.0 - PER_KM * 12.0 - 1.0 * (20.0 + 100.0))
    assert deferred == 0.0


@pytest.mark.unit
def test_deferral_costs_the_users_waiting_minute() -> None:
    """With a waiting cost a deferral pays minus that cost, an offer is unchanged."""
    problem, simulation = start_episode(
        [FakeVehicle("Vehicle_1")],
        problem=AdmissionProblem(Surplus(wait_cost_per_min=0.3)),
    )
    search = make_search([(0.0, 1000.0, 5.0)])

    decide(problem, simulation, search, DEFER)
    settle(problem, simulation, 0.0, 1.0)
    deferred = problem.compute_reward(simulation, Period(0.0, 1.0))
    decide(problem, simulation, search, OFFER)
    settle(problem, simulation, 1.0, 2.0)
    offered = problem.compute_reward(simulation, Period(1.0, 2.0))

    assert deferred == pytest.approx(-0.3)
    assert offered == pytest.approx(5.0 - PER_KM * 1.0)


@pytest.mark.unit
def test_negative_waiting_cost_is_rejected() -> None:
    """A waiting cost below zero would pay for deferring and fails at construction."""
    with pytest.raises(ValueError, match="zero or more"):
        Surplus(wait_cost_per_min=-1.0)


@pytest.mark.unit
@pytest.mark.parametrize("reward", ["surplus", Surplus])
def test_reward_other_than_a_reward_instance_is_rejected(reward: object) -> None:
    """A string or a bare reward class fails at construction rather than at the first step."""
    with pytest.raises(TypeError, match="Reward"):
        AdmissionProblem(reward)  # type: ignore[arg-type]


@pytest.mark.unit
def test_pickup_beyond_the_radius_is_clipped() -> None:
    """A pickup leg past the configured radius still lies in the observation space."""
    problem, simulation = start_episode([FakeVehicle("Vehicle_1")])
    search = make_search([(2 * RADIUS_M, 500.0, 5.0)])

    observation = problem.build_observation(simulation, PERIOD, make_request(search))

    assert observation[FEATURES.index("pickup")] == 1.0
    assert observation in problem.observation_space


@pytest.mark.unit
def test_alternative_without_a_pickup_route_is_rejected() -> None:
    """The search sets a route to pickup on every alternative, so None is a bug, not a vehicle at the origin."""
    problem, simulation = start_episode([FakeVehicle("Vehicle_1")])
    search = make_search([(0.0, 100.0, 5.0)])
    search.alternatives[0].route_to_pickup = None

    with pytest.raises(ValueError, match="route to pickup"):
        problem.build_observation(simulation, PERIOD, make_request(search))


@pytest.mark.unit
def test_payload_other_than_a_search_is_rejected() -> None:
    """A pending decision from another seam fails the observation and the action."""
    problem, simulation = start_episode([FakeVehicle("Vehicle_1")])
    request = make_request(payload=None)

    with pytest.raises(TypeError, match="Search"):
        problem.build_observation(simulation, PERIOD, request)
    with pytest.raises(TypeError, match="Search"):
        problem.apply_action(simulation, request, np.int64(OFFER))


@pytest.mark.unit
def test_decision_of_another_operator_is_rejected() -> None:
    """A search another operator sent to the shared broker is rejected before it is observed."""
    problem, simulation = start_episode([FakeVehicle("Vehicle_1")])
    request = make_request(
        make_search([(0.0, 100.0, 5.0)]), requester_id=SimId("Operator_other")
    )

    with pytest.raises(ValueError, match="Operator_other"):
        problem.on_request(simulation, request)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("action", "offers"),
    [(OFFER, True), (DEFER, False), (np.int64(OFFER), True), (np.array(DEFER), False)],
)
def test_action_becomes_the_reply_and_is_counted(action: object, offers: bool) -> None:
    """The reply is the bool the action stands for and info counts it beside the period's settlement."""
    problem, simulation = start_episode([FakeVehicle("Vehicle_1")])

    reply = decide(problem, simulation, make_search([(0.0, 100.0, 5.0)]), action)

    assert reply is offers
    settle(problem, simulation, 0.0, 15.0, revenue=5.0)
    info = problem.info(simulation, PERIOD)
    assert (info["offered"], info["deferred"]) == ((1, 0) if offers else (0, 1))
    assert info["profit"] == 5.0


@pytest.mark.unit
def test_action_outside_the_space_is_rejected() -> None:
    """An action that is neither DEFER nor OFFER fails before it becomes a reply."""
    problem, simulation = start_episode([FakeVehicle("Vehicle_1")])

    with pytest.raises(ValueError, match="defer"):
        problem.apply_action(
            simulation, make_request(make_search([(0.0, 100.0, 5.0)])), np.int64(2)
        )


@pytest.mark.unit
def test_search_engine_other_than_the_adapter_is_rejected() -> None:
    """An episode whose search engine would ignore the reply fails at its start."""
    simulation = make_simulation([FakeVehicle("Vehicle_1")])
    wire(simulation)
    operator_of(simulation).search_engine = SimpleNamespace()
    problem = AdmissionProblem()

    with pytest.raises(TypeError, match="BrokeredAdmissionSearchEngine"):
        problem.on_episode_start(simulation)


@pytest.mark.unit
def test_operations_without_a_pickup_radius_are_rejected() -> None:
    """Operations that are not ride-hailing ones fail at the episode start, typed."""
    simulation = make_simulation([FakeVehicle("Vehicle_1")])
    wire(simulation)
    operator_of(simulation).operations.config = SimpleNamespace()
    problem = AdmissionProblem()

    with pytest.raises(TypeError, match="RideHailingOperationsConfig"):
        problem.on_episode_start(simulation)


@pytest.mark.unit
def test_operator_without_vehicles_is_rejected() -> None:
    """An empty fleet fails at the episode start, before any observation."""
    simulation = make_simulation([])
    wire(simulation)
    problem = AdmissionProblem()

    with pytest.raises(ValueError, match="at least one vehicle"):
        problem.on_episode_start(simulation)


def run(env: UmosimEnv, action: int) -> tuple[list[float], list[dict[str, Any]]]:
    """Run one seeded episode answering every search with ``action``.

    Returns the rewards and the info of every step.
    """
    env.reset(seed=7)
    rewards: list[float] = []
    infos: list[dict[str, Any]] = []
    while True:
        _, reward, terminated, truncated, info = env.step(action)
        rewards.append(reward)
        infos.append(info)
        if terminated or truncated:
            return rewards, infos


def revenue(infos: list[dict[str, Any]]) -> float:
    """Return the revenue of the learning agent's operator over the stepped periods."""
    return sum(info["revenue"] for info in infos)


@pytest.mark.integration
@pytest.mark.slow
def test_offered_searches_pay_and_deferred_ones_cannot(
    make_env: Callable[..., UmosimEnv],
) -> None:
    """The reply reaches the users' searches through the adapter.

    A deferred user searches again a minute later, so deferring everything asks
    more often than offering everything and still earns nothing. The offering
    episode runs second, so a fresh episode is shown to book its trips.
    """
    env = make_env(AdmissionProblem())

    _, deferred = run(env, DEFER)
    _, offered = run(env, OFFER)

    assert revenue(offered) > 0
    assert offered[-1]["offered"] > 0
    assert offered[-1]["deferred"] == 0
    assert revenue(deferred) == 0
    assert deferred[-1]["offered"] == 0
    assert deferred[-1]["deferred"] > offered[-1]["offered"]


@pytest.mark.integration
@pytest.mark.slow
def test_surplus_is_priced_on_the_simulations_own_alternatives(
    make_env: Callable[..., UmosimEnv],
) -> None:
    """The surplus reads the real alternatives and vehicles, not the fakes.

    At the first decision the yield is still zero, so the first reward is positive.
    By the horizon the fleet has earned a yield.
    """
    problem = AdmissionProblem(Surplus())

    rewards, _ = run(make_env(problem), OFFER)

    assert np.isfinite(rewards).all()
    assert rewards[0] > 0
    assert problem.fleet_yield > 0


@pytest.mark.integration
@pytest.mark.slow
def test_env_passes_the_gymnasium_checker(make_env: Callable[..., UmosimEnv]) -> None:
    """Discrete actions over a flat observation satisfy the Gymnasium contract."""
    check_env(make_env(AdmissionProblem()), skip_render_check=True)
