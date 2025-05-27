from abc import ABC, abstractmethod

from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transportation_search_task import TransportationSearchTask


class SearchEngineInterface(ABC):
    def register_fleet(self, fleet: VehicleFleet):  # noqa: ANN201
        # TODO: can we omit this and have search engines always refer to the operator's fleet?
        self._fleet = fleet

    @abstractmethod
    def search_for_transportation_alternatives(
        self, vehicle_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        pass  # Implement filtering
