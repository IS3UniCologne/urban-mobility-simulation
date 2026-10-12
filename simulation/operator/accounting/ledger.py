"""Operator-owned ledger and the contracts vehicles and workers report through."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from simulation.helper.time import MINUTES_PER_DAY, MINUTES_PER_HOUR
from simulation.operator.accounting.cost_type import CostType

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import (
        VehicleCostConfig,
        WorkerCostConfig,
    )
    from simulation.helper.types import SimId

logger = logging.getLogger(__name__)


class CostBearingVehicle(Protocol):
    """Structural type a vehicle must satisfy to be cost-tracked."""

    @property
    def uid(self) -> SimId:
        """Identity the ledger attributes costs to."""

    @property
    def cost_config(self) -> VehicleCostConfig:
        """Operator cost rates for this vehicle."""


class CostBearingWorker(Protocol):
    """Structural type a service worker must satisfy to be cost-tracked."""

    @property
    def uid(self) -> SimId:
        """Identity the ledger attributes costs to."""

    @property
    def cost_config(self) -> WorkerCostConfig:
        """Operator cost rates for this worker."""


class VehicleLedger(ABC):
    """Ledger as a vehicle reports to it."""

    __slots__ = ()

    @abstractmethod
    def register_vehicle(self, vehicle: CostBearingVehicle) -> None:
        """Start cost tracking for a vehicle.

        Parameters
        ----------
        vehicle : CostBearingVehicle
            Vehicle to track. The daily rate accrues from now on.
        """

    @abstractmethod
    def record_distance(
        self, vehicle: CostBearingVehicle, distance_m: float, relocation: bool
    ) -> None:
        """Report distance driven by a vehicle.

        Parameters
        ----------
        vehicle : CostBearingVehicle
            Vehicle that moved.
        distance_m : float
            Distance in meters.
        relocation : bool
            Whether the movement was empty repositioning.
        """

    @abstractmethod
    def record_energy_charged(
        self, vehicle: CostBearingVehicle, kwh: float, cost_per_kWh: float
    ) -> None:
        """Report energy charged into a vehicle.

        Parameters
        ----------
        vehicle : CostBearingVehicle
            Vehicle that charged.
        kwh : float
            Actually charged energy in kWh.
        cost_per_kWh : float
            Cost per kWh the operator pays for the energy.
        """

    @abstractmethod
    def report_fulfilled_trip(self, vehicle: CostBearingVehicle, price: float) -> None:
        """Report a fulfilled trip's fare.

        Report every fulfilled trip. The driver share comes from the vehicle's
        own cost config.

        Parameters
        ----------
        vehicle : CostBearingVehicle
            Vehicle that served the trip.
        price : float
            Gross trip price paid by the user.
        """


class WorkerLedger(ABC):
    """Ledger as a service worker reports to it."""

    __slots__ = ()

    @abstractmethod
    def register_worker(self, worker: CostBearingWorker, active: bool) -> None:
        """Start cost tracking for a service worker.

        Parameters
        ----------
        worker : CostBearingWorker
            Worker to track. Time cost accrues from now on while active.
        active : bool
            Whether the worker starts in an active (paid) state.
        """

    @abstractmethod
    def set_worker_active(self, worker: CostBearingWorker, active: bool) -> None:
        """Report a change of a worker's activity for time-cost accrual.

        Parameters
        ----------
        worker : CostBearingWorker
            Worker whose activity changed.
        active : bool
            Whether the worker is now active (paid). No-op if unchanged.
        """


@dataclass(slots=True)
class _TimeAccrual:
    """Time-based cost accrual for a single entity.

    Attributes
    ----------
    since : float
        Simulation time the currently open span started.
    active : bool
        Whether the entity is currently in its active state.
    rate : float
        Cost per minute while active.
    cost_type : CostType
        Cost type the accrual books to.
    """

    since: float
    active: bool
    rate: float
    cost_type: CostType


class Ledger(VehicleLedger, WorkerLedger):
    """
    Accumulate operator revenue and costs from raw quantities reported by components.

    Keeps running cost totals per cost type and entity and one gross revenue
    total; time-based costs are settled lazily on every query, so totals are
    correct at any simulation time without per-tick work.

    Parameters
    ----------
    sim : SimulationContext
        Simulation context supplying the clock accruals are folded against.
    """

    __slots__ = ("_costs", "_env", "_revenue", "_time_accruals")

    def __init__(self, sim: SimulationContext) -> None:
        self._env = sim.env
        self._costs: defaultdict[CostType, defaultdict[SimId, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self._time_accruals: dict[SimId, _TimeAccrual] = {}
        self._revenue = 0.0

    # Vehicle reporting

    def register_vehicle(self, vehicle: CostBearingVehicle) -> None:
        """Start cost tracking for a vehicle."""
        self._time_accruals[vehicle.uid] = _TimeAccrual(
            since=self._env.now,
            active=True,
            rate=vehicle.cost_config.DAILY / MINUTES_PER_DAY,
            cost_type=CostType.VEHICLE_HOLDING,
        )

    def record_distance(
        self, vehicle: CostBearingVehicle, distance_m: float, relocation: bool
    ) -> None:
        """Report distance driven by a vehicle, in meters."""
        cost_type = (
            CostType.VEHICLE_RELOCATION_DISTANCE
            if relocation
            else CostType.VEHICLE_DISTANCE
        )
        cost_per_km = vehicle.cost_config.PER_KM
        self._costs[cost_type][vehicle.uid] += distance_m / 1000 * cost_per_km

    def record_energy_charged(
        self, vehicle: CostBearingVehicle, kwh: float, cost_per_kWh: float | None = None
    ) -> None:
        """Report energy actually charged into a vehicle, in kWh."""
        if cost_per_kWh is None:
            cost_per_kWh = vehicle.cost_config.CHARGING_PER_KWH
        self._costs[CostType.VEHICLE_CHARGING][vehicle.uid] += kwh * cost_per_kWh

    def report_fulfilled_trip(self, vehicle: CostBearingVehicle, price: float) -> None:
        """Book a fulfilled trip's gross price as revenue and its driver share as cost."""
        self._revenue += price
        share = vehicle.cost_config.DRIVER_PAYMENT_SHARE
        if share > 0:
            self._costs[CostType.DRIVER_PAYMENT][vehicle.uid] += price * share

    # Worker reporting

    def register_worker(self, worker: CostBearingWorker, active: bool) -> None:
        """Start cost tracking for a service worker."""
        self._time_accruals[worker.uid] = _TimeAccrual(
            since=self._env.now,
            active=active,
            rate=worker.cost_config.HOURLY / MINUTES_PER_HOUR,
            cost_type=CostType.WORKER_LABOR,
        )

    def set_worker_active(self, worker: CostBearingWorker, active: bool) -> None:
        """Report a change of a worker's activity. No-op if unchanged."""
        self._flip_accrual(worker.uid, active=active)

    def revenue(self) -> float:
        """Return gross revenue."""
        return self._revenue

    def costs_by_type(self) -> dict[CostType, float]:
        """Return accumulated cost per cost type, zero for unused types."""
        self._settle(self._env.now)
        return {
            cost_type: sum(self._costs[cost_type].values()) for cost_type in CostType
        }

    def costs_by_entity(self, cost_type: CostType | None = None) -> dict[SimId, float]:
        """Return accumulated cost per entity.

        Parameters
        ----------
        cost_type : CostType or None
            Restrict to one cost type. None sums across all types.

        Returns
        -------
        dict[SimId, float]
            Mapping of entity ID to total cost incurred.
            The result is sparse: an entity absent has no incurred cost of the requested type.
        """
        self._settle(self._env.now)
        if cost_type is not None:
            return dict(self._costs[cost_type])
        result: defaultdict[SimId, float] = defaultdict(float)
        for by_entity in self._costs.values():
            for uid, amount in by_entity.items():
                result[uid] += amount
        return dict(result)

    def _flip_accrual(self, uid: SimId, active: bool) -> None:
        """Fold the open time span of an entity and switch its activity flag."""
        accrual = self._time_accruals.get(uid)
        if accrual is None:
            logger.debug("Activity reported for unregistered entity %s.", uid)
            return
        if accrual.active == active:
            return
        self._fold(accrual, uid, self._env.now)
        accrual.active = active

    def _fold(self, accrual: _TimeAccrual, uid: SimId, now: float) -> None:
        """Fold the open time span of one accrual into costs up to now."""
        elapsed = now - accrual.since
        accrual.since = now
        if not accrual.active or elapsed <= 0 or accrual.rate <= 0:
            return
        self._costs[accrual.cost_type][uid] += elapsed * accrual.rate

    def _settle(self, now: float) -> None:
        """Fold all open time accruals into costs up to now."""
        for uid, accrual in self._time_accruals.items():
            self._fold(accrual, uid, now)
