import logging

from simpy import Environment

from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import (
    TransportationAlternativeRideHailing,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operator import Operator
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transport_task import TransportTask


class RideHailingOperator(Operator):
    def __init__(
        self,
        env: Environment,
        fleet: VehicleFleet,
        charging_infrastructure: ChargingInfrastructure,
        operations: OperationsInterface,
        search_engine: SearchEngineInterface,
        allocation_engine: VehicleAllocationEngineInterface,
    ):
        super().__init__(
            env,
            fleet,
            charging_infrastructure,
            operations,
            search_engine,
            allocation_engine,
        )

        self._driver_payment_share = (
            Configuration().ride_hailing_global.DRIVER_PAYMENT_SHARE
        )

    def pay_for_fulfilled_transportation_task(
        self,
        user,
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternativeRideHailing,
    ):
        payment = selected_transportation_alternative.price
        vehicle = selected_transportation_alternative.vehicle
        # we need to pay the driver costs
        if vehicle.__class__.__name__ == "RideHailingCar":
            self.increase_total_revenue(payment * (1 - self._driver_payment_share))
            vehicle.update_earned_money(payment)

        else:
            self.increase_total_revenue(payment)

        # Add Transaction to Log
        self._transactions.append(
            {
                "vehicle_id": selected_transportation_alternative.vehicle.id,
                "origin": selected_transportation_alternative.route.origin.get_hexagon()[
                    0
                ],
                "destination": selected_transportation_alternative.route.destination.get_hexagon()[
                    0
                ],
                "time_start": transportation_task.time,
                "time_end": self._env.now,
                "price": selected_transportation_alternative.price,
                "distance": selected_transportation_alternative.distance,
                "duration": selected_transportation_alternative.duration,
                "wait_time": transportation_task.actual_wait_time,
                "energy_consumption": selected_transportation_alternative.energy_consumed,
                "waiting_time": selected_transportation_alternative.waiting_time,
                "pick_up_time": selected_transportation_alternative.pick_up_time,
                "selected_vehicle_mode": selected_transportation_alternative.vehicle.__class__.__name__
                + "_"
                + str(selected_transportation_alternative.vehicle.is_electric),
                "selected_vehicle_EV": selected_transportation_alternative.vehicle.is_electric,
                "state": "Fulfilled",
                **transportation_task.viable_vehicle_modes,
            }
        )

        logging.info(
            f"New Payment ({payment}) received from User {user.id}. Current Total Revenue: {self.total_revenue}.",
            extra={"clazz": self.__class__.__name__, "oid": self._fleet.id},
        )

    def withdraw_transportation_task(
        self, user, transportation_task: TransportTask, state=None
    ):
        # distance = transportation_task.origin >> transportation_task.destination
        # TODO: define price of the trip

        self.increase_total_missed_trips(1)

        # Add Transaction to Log
        self._transactions.append(
            {
                "origin": transportation_task.origin.get_hexagon(return_geom=False)[0],
                "destination": transportation_task.destination.get_hexagon(
                    return_geom=False
                )[0],
                "time_start": self._env.now,
                "time_end": self._env.now,
                "price": 0.0,
                "distance": transportation_task.origin
                >> transportation_task.destination,
                "duration": 0.0,
                "energy_consumption": 0.0,
                "waiting_time": user._waiting_time,
                "pick_up_time": 0.0,
                "selected_vehicle_mode": "None",
                "selected_vehicle_EV": "None",
                "state": state,
                **transportation_task.viable_vehicle_modes,
            }
        )

        logging.info(
            f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",
            extra={"clazz": self.__class__.__name__, "oid": self._fleet.id},
        )
