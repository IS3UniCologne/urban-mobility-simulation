from abc import ABC, abstractmethod

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
