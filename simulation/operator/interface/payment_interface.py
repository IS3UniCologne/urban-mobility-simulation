from abc import ABC, abstractmethod

import pandas as pd

from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.tasks.transport_task import TransportTask

# TODO: an interface should not implement functionality?
class PaymentInterface(ABC):
    def __init__(self):
        self._total_revenue = 0
        self._total_fulfilled_trips = 0
        self._total_missed_trips = 0
        self._total_missed_revenue = 0

        # Make this dynamic with a dictionary
        self._total_missed_car_trips = 0

        self._transactions = []

        # only for bus tracking
        self._tracked_demands = set()

    @abstractmethod
    def pay_for_fulfilled_transportation_task(
        self,
        user,
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ):
        pass

    @abstractmethod
    def withdraw_transportation_task(self, user, transportation_task: TransportTask):
        pass

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
