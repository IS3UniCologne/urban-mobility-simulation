from abc import ABC, abstractmethod

import pandas as pd

from simulation.operator.data_transfer_object.transportation_alternative import TransportationAlternative
from simulation.tasks.transport_task import TransportTask


class PaymentInterface(ABC):

    def __init__(self):
        self._total_revenue = 0
        self._total_fulfilled_trips = 0
        self._total_missed_trips = 0

        self._transactions = []

    @abstractmethod
    def pay_for_fulfilled_transportation_task(self, user, transportation_task: TransportTask, selected_transportation_alternative: TransportationAlternative):
        pass

    @abstractmethod
    def withdraw_transportation_task(self, transportation_task:TransportTask):
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

    def increase_total_revenue(self, additional_revenue):
        self._total_fulfilled_trips += 1
        self._total_revenue += additional_revenue

    def increase_total_missed_trips(self):
        self._total_missed_trips += 1