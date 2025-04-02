import logging

from simpy import Environment

from simulation.helper.configuration.configuration import Configuration
from simulation.helper.configuration.enums import VehicleMode
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operator import Operator
from simulation.operator.service_workforce import ServiceWorkforce
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transport_task import TransportTask


class SharedMobilityOperator(Operator):

    __slots__ = ("_number_service_workers", "_workforce")
    def __init__(
        self,
        env: Environment,
        fleet: VehicleFleet,
        charging_infrastructure: ChargingInfrastructure,
        operations: OperationsInterface,
        search_engine: SearchEngineInterface,
        allocation_engine: VehicleAllocationEngineInterface,
        number_service_workers: int,
    ):
        super(SharedMobilityOperator, self).__init__(
            env,
            fleet,
            charging_infrastructure,
            operations,
            search_engine,
            allocation_engine,
        )

        # Shared Mobility specific: Service Workforce
        self._workforce = ServiceWorkforce(
            env=self._env, number_service_workers=number_service_workers
        )

    def withdraw_transportation_task(self, user, transportation_task: TransportTask):
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

                if vehicle_type == "SharedKickScooter":
                    missed_trip_cost += 1.0  # Unlock Fee

        self.increase_total_missed_trips(missed_trip_cost)

        # Add Transaction to Log
        self._transactions.append(
            {
                "vehicle_id": None,
                "origin": transportation_task.origin.get_hexagon_id(),
                "destination": transportation_task.destination.get_hexagon_id(),
                "time_start": self._env.now,
                "time_end": self._env.now,
                "price": 0.0,
                "distance": transportation_task.origin
                >> transportation_task.destination,
                "duration": 0.0,
                "wait_time": transportation_task.actual_wait_time,
                "energy_consumption": 0.0,
                "selected_vehicle_mode": "None",
                "state": "Missed",
                **transportation_task.viable_vehicle_modes,
            }
        )

        logging.info(
            f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )
