from __future__ import annotations  # noqa: D100

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.operator.data_transfer_object.transport_request import (
        TransportRequest,
    )
    from simulation.operator.data_transfer_object.transportation_alternative_browser import (
        TransportationAlternativeBrowser,
    )


class SearchEngineInterface(ABC):
    """Interface for search engines.

    This defines the contract for all search engines in the simulation.
    """

    @abstractmethod
    def search_for_transportation_alternatives(  # noqa: D102
        self, transport_task: TransportRequest
    ) -> TransportationAlternativeBrowser:
        pass  # Implement filtering
