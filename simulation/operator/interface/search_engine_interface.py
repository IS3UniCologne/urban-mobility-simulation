from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.operator.data_transfer_object.transportation_alternative_browser import (
        TransportationAlternativeBrowser,
    )
    from simulation.tasks.transportation_search_task import TransportationSearchTask


class SearchEngineInterface(ABC):
    """Interface for search engines.

    This defines the contract for all search engines in the simulation.
    """

    @abstractmethod
    def search_for_transportation_alternatives(
        self, vehicle_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        pass  # Implement filtering
