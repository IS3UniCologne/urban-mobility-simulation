from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.agent.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.interface.search_engine_interface import (
        SearchEngineInterface,
    )
    from simulation.operator.interface.vehicle_allocation_engine_interface import (
        AllocationEngineInterface,
    )
    from simulation.operator.operations_management.integrated_shared_mobility_operations import (
        IntegratedSharedMobilityOperations,
    )
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.tasks.transport_task import TransportTask

from simulation.helper.configuration.enums import OperatorMode, TransactionState
from simulation.operator.operator import Operator
from simulation.operator.service_workforce import ServiceWorkforce
from simulation.operator.transactions import DemandMonitor


class SharedMobilityOperator(Operator):  # noqa: D101
    __slots__ = ("_demand_monitor", "_number_service_workers", "_workforce")

    def __init__(  # noqa: ANN204
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        operations: IntegratedSharedMobilityOperations,
        search_engine: SearchEngineInterface,
        allocation_engine: AllocationEngineInterface,
        number_service_workers: int,
    ):
        super().__init__(
            sim=sim,
            fleet=fleet,
            operations=operations,
            search_engine=search_engine,
            allocation_engine=allocation_engine,
        )
        self._mode = OperatorMode.SHARED_MOBILITY
        # Register demand monitor to transaction log
        self._demand_monitor: DemandMonitor = DemandMonitor(
            operations._available_vehicle_types  # noqa: SLF001
        )
        self._transaction_log.add_listener(self._demand_monitor)

        # Shared Mobility specific: Service Workforce
        self._workforce = ServiceWorkforce(
            sim=self._sim, number_service_workers=number_service_workers
        )

    @property
    def demand_monitor(self) -> DemandMonitor:
        """
        Demand monitor for the operator.

        Returns
        -------
        DemandMonitor
            The demand monitor instance.
        """
        return self._demand_monitor

    def withdraw_transportation_task(  # noqa: ANN201, D102
        self, user: User, transportation_task: TransportTask
    ):
        # vehicle_types = [
        #     mode.name
        #     for mode in self._config.shared_vehicle_global.AVAILABLE_VEHICLE_MODES
        # ]

        # We assume an ordered list here (e.g., SharedCar, SharedScooter, SharedKickScooter)
        # We count the lost revenue for the "cheapest" mode
        # TODO: Do this somewhere else and not every time a task is withdrawn (vectorize this)
        # for vehicle_type in vehicle_types:
        #     if (
        #         vehicle_type in transportation_task.viable_vehicle_modes
        #         and transportation_task.viable_vehicle_modes[vehicle_type] == 1
        #     ):
        #         distance = transportation_task.origin >> transportation_task.destination
        #         velocity = (
        #             Configuration()
        #             .shared_vehicles.get(VehicleMode[vehicle_type])
        #             .VELOCITY
        #         )
        #         price_per_min = (
        #             Configuration()
        #             .shared_vehicles.get(VehicleMode[vehicle_type])
        #             .PRICE_PER_MIN
        #         )
        #         missed_trip_cost = distance / velocity * price_per_min

        #         if vehicle_type == "KickScooter":
        #             missed_trip_cost += 1.0  # Unlock Fee

        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=None,
            state=TransactionState.MISSED,
            trip_record=None,
        )

        self.logger.info("Missed trip of User %s.", user.uid)
