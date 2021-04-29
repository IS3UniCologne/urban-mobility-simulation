from abc import ABC, abstractmethod

from simulation.operator.data_transfer_object.transportation_alternative import TransportationAlternative

class PaymentInterface(ABC):

    def __init__(self):
        self._total_revenue = 0

    @abstractmethod
    def pay_for_fulfilled_transportation_task(self, user, selected_transportation_alternative: TransportationAlternative):
        pass

    @property
    def total_revenue(self):
        return self._total_revenue

    def increase_total_revenue(self, additional_revenue):
        self._total_revenue += additional_revenue