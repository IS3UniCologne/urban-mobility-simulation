"""Reporting contract between cost-incurring components and the cost ledger."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from simulation.helper.configuration.configuration import (
        VehicleCostConfig,
        WorkerCostConfig,
    )
    from simulation.helper.types import SimId


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


class VehicleCostReporter(ABC):
    """Contract for reporting cost-relevant vehicle quantities."""

    __slots__ = ()

    @abstractmethod
    def register_vehicle(self, vehicle: CostBearingVehicle, active: bool) -> None:
        """Start cost tracking for a vehicle.

        Parameters
        ----------
        vehicle : CostBearingVehicle
            Vehicle to track. Time-based costs accrue from now on.
        active : bool
            Whether the vehicle starts in an active (online) state.
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
    def record_energy_charged(self, vehicle: CostBearingVehicle, kwh: float) -> None:
        """Report energy charged into a vehicle.

        Parameters
        ----------
        vehicle : CostBearingVehicle
            Vehicle that charged.
        kwh : float
            Actually charged energy in kWh.
        """

    @abstractmethod
    def set_vehicle_active(self, vehicle: CostBearingVehicle, active: bool) -> None:
        """Report a change of a vehicle's activity for time-based costs.

        Parameters
        ----------
        vehicle : CostBearingVehicle
            Vehicle whose activity changed.
        active : bool
            Whether the vehicle is now active (online). No-op if unchanged.
        """

    @abstractmethod
    def report_driver_trip_compensation(
        self, vehicle: CostBearingVehicle, price: float
    ) -> None:
        """Report a completed trip fare that a driver is paid a share of.

        Report every fulfilled trip. The share comes from the vehicle's own
        cost config.

        Parameters
        ----------
        vehicle : CostBearingVehicle
            Vehicle that served the trip.
        price : float
            Gross trip price paid by the user.
        """


class WorkerCostReporter(ABC):
    """Contract for reporting cost-relevant service worker quantities."""

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


class NullVehicleCostReporter(VehicleCostReporter):
    """No-op reporter for vehicles without cost accounting."""

    __slots__ = ()

    def register_vehicle(self, vehicle: CostBearingVehicle, active: bool) -> None:
        """Ignore vehicle registration."""

    def record_distance(
        self, vehicle: CostBearingVehicle, distance_m: float, relocation: bool
    ) -> None:
        """Ignore distance report."""

    def record_energy_charged(self, vehicle: CostBearingVehicle, kwh: float) -> None:
        """Ignore charging report."""

    def set_vehicle_active(self, vehicle: CostBearingVehicle, active: bool) -> None:
        """Ignore vehicle activity change."""

    def report_driver_trip_compensation(
        self, vehicle: CostBearingVehicle, price: float
    ) -> None:
        """Ignore fare report."""


class NullWorkerCostReporter(WorkerCostReporter):
    """No-op reporter for service workers without cost accounting."""

    __slots__ = ()

    def register_worker(self, worker: CostBearingWorker, active: bool) -> None:
        """Ignore worker registration."""

    def set_worker_active(self, worker: CostBearingWorker, active: bool) -> None:
        """Ignore worker activity change."""


NULL_VEHICLE_COST_REPORTER: VehicleCostReporter = NullVehicleCostReporter()
NULL_WORKER_COST_REPORTER: WorkerCostReporter = NullWorkerCostReporter()
