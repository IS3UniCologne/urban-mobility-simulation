import logging

from simpy import Environment

from simulation.agent.user import User
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.configuration.enums import VehicleMode
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)
from simulation.operator.operations_management.integrated_shared_mobility_operations import (
    IntegratedSharedMobilityOperations,
)
from simulation.operator.operator import Operator
from simulation.operator.service_workforce import ServiceWorkforce
from simulation.operator.transactions import DemandTracker
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transport_task import TransportTask


class SharedMobilityOperator(Operator):
    __slots__ = ("_demand_tracker", "_number_service_workers", "_workforce")

    def __init__(  # noqa: ANN204
        self,
        env: Environment,
        fleet: VehicleFleet,
        charging_infrastructure: ChargingInfrastructure,
        operations: IntegratedSharedMobilityOperations,
        search_engine: SearchEngineInterface,
        allocation_engine: VehicleAllocationEngineInterface,
        number_service_workers: int,
    ):
        super().__init__(
            env,
            fleet,
            charging_infrastructure,
            operations,
            search_engine,
            allocation_engine,
        )
        # Register demand tracker to transaction log
        self._demand_tracker: DemandTracker = DemandTracker(
            operations._available_vehicle_modes  # noqa: SLF001
        )
        self._transaction_log.add_listener(self._demand_tracker)

        # Shared Mobility specific: Service Workforce
        self._workforce = ServiceWorkforce(
            env=self._env, number_service_workers=number_service_workers
        )

    @property
    def demand_tracker(self) -> DemandTracker:
        """
        Demand tracker for the operator.

        Returns
        -------
        DemandTracker
            The demand tracker instance.
        """
        return self._demand_tracker

    def withdraw_transportation_task(  # noqa: ANN201
        self, user: User, transportation_task: TransportTask
    ):
        vehicle_types = [
            mode.name
            for mode in Configuration().shared_vehicle_global.AVAILABLE_VEHICLE_MODES
        ]

        # We assume an ordered list here (e.g., SharedCar, SharedScooter, SharedKickScooter)
        # We count the lost revenue for the "cheapest" mode
        for vehicle_type in vehicle_types:
            if (
                vehicle_type in transportation_task.viable_vehicle_modes
                and transportation_task.viable_vehicle_modes[vehicle_type] == 1
            ):
                distance = transportation_task.origin >> transportation_task.destination
                velocity = (
                    Configuration()
                    .shared_vehicles.get(VehicleMode[vehicle_type])
                    .VELOCITY
                )
                price_per_min = (
                    Configuration()
                    .shared_vehicles.get(VehicleMode[vehicle_type])
                    .PRICE_PER_MIN
                )
                missed_trip_cost = distance / velocity * price_per_min

                if vehicle_type == "KickScooter":
                    missed_trip_cost += 1.0  # Unlock Fee

        self.increase_total_missed_trips(missed_trip_cost)

        self.log_transaction(
            transportation_task=transportation_task,
            transportation_alternative=None,
            state="Missed",
            trip_record=None,
        )

        logging.info(
            f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",  # noqa: G004
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )
