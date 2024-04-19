import logging

import pandas as pd
from simpy import Environment

from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transport_task import TransportTask


class Operator:
    def __init__(
        self,
        env: Environment,
        fleet: VehicleFleet,
        charging_infrastructure: ChargingInfrastructure,
        operations: OperationsInterface,
        search_engine: SearchEngineInterface,
        allocation_engine: VehicleAllocationEngineInterface,
    ):
        self._env = env
        self._fleet = fleet
        self.charging_infastructure = charging_infrastructure
        self._operations = operations

        self._search_engine = search_engine
        self._allocation_engine = allocation_engine

        self._total_revenue = 0
        self._total_fulfilled_trips = 0
        self._total_missed_trips = 0
        self._total_missed_revenue = 0

        self._transactions = []

        self._operations.register_operator_reference(self)

        self._search_engine.register_fleet(self._fleet)

    @property
    def total_revenue(self):
        return self._total_revenue

    @property
    def total_fulfilled_trips(self):
        return self._total_fulfilled_trips

    @property
    def total_missed_trips(self):
        return self._total_missed_trips

    @property
    def total_missed_revenue(self):
        return self._total_missed_revenue

    @property
    def fleet(self):
        return self._fleet

    def increase_total_revenue(self, additional_revenue):
        self._total_fulfilled_trips += 1
        self._total_revenue += additional_revenue

    def increase_total_missed_trips(self, missed_revenue):
        self._total_missed_revenue += missed_revenue
        self._total_missed_trips += 1

    def get_transactions(self):
        """
        Return all transactions (fulfilled and missed) as a DataFrame

        DataFrame has the following columns
        "origin": Origin of Request
        "destination": Destination of Request
        "time_start": Trip Request Start Time
        "time_end": Trip Request End Time
        "price": Trip Price (0.0 if missed)
        "distance": (Expected) distance,
        "duration": Duration in minutes, 0.0 if missed
        "selected_vehicle_mode": Selected Vehicle Mode
        "state": Missed or Fulfilled
        "viable_vehicle_modes": List of viable modes for this trip (set 1 and 0 columnwise per Vehicle)

        :return: DataFrame
        """
        return pd.DataFrame(self._transactions)

    def pay_for_fulfilled_transportation_task(
        self,
        user,
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ):
        payment = selected_transportation_alternative.price
        self.increase_total_revenue(payment)

        # Add Transaction to Log
        self._transactions.append(
            {
                "origin": selected_transportation_alternative.route.origin.get_default_hexagon(),
                "destination": selected_transportation_alternative.route.destination.get_default_hexagon(),
                "time_start": transportation_task.time,
                "time_end": self._env.now,
                "price": selected_transportation_alternative.price,
                "distance": selected_transportation_alternative.distance,
                "duration": selected_transportation_alternative.duration,
                "energy_consumption": selected_transportation_alternative.energy_consumed,
                "selected_vehicle_mode": selected_transportation_alternative.vehicle.__class__.__name__,
                "state": "Fulfilled",
                **transportation_task.viable_vehicle_modes,
            }
        )

        logging.info(
            f"New Payment ({payment}) received from User {user.id}. Current Total Revenue: {self.total_revenue}.",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

    def withdraw_transportation_task(self, user, transportation_task: TransportTask):
        self.increase_total_missed_trips(0)

        # Add Transaction to Log
        self._transactions.append(
            {
                "origin": transportation_task.origin.get_default_hexagon(),
                "destination": transportation_task.destination.get_default_hexagon(),
                "time_start": self._env.now,
                "time_end": self._env.now,
                "price": 0.0,
                "distance": transportation_task.origin
                >> transportation_task.destination,
                "duration": 0.0,
                "energy_consumption": 0.0,
                "selected_vehicle_mode": "None",
                "state": "Missed",
                **transportation_task.viable_vehicle_modes,
            }
        )

        logging.debug(
            f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )
