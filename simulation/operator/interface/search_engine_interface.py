from abc import ABC, abstractmethod

from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.tasks.transportation_search_task import TransportationSearchTask


class SearchEngineInterface(ABC):
    @abstractmethod
    def search_for_transportation_alternatives(
        self, vehicle_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        pass  # Implement filtering
        # return []
