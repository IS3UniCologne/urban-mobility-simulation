"""Seam adapter for the search engine.

The broker decides for each ride request whether the user gets the vehicles the search found.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine

if TYPE_CHECKING:
    from simulation.operator.data_transfer_object.transport_request import (
        TransportRequest,
    )
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.search_engine import SearchEngineDependencies


@dataclass(frozen=True, slots=True)
class Search:
    """
    A ride request and the alternatives the search found for it.

    The search engine gives one to the broker with each admission decision.

    Attributes
    ----------
    transport_request : TransportRequest
        Request the user searched with.
    alternatives : tuple of TransportationAlternative
        Alternatives the plain search found, at least one.
    """

    transport_request: TransportRequest
    alternatives: tuple[TransportationAlternative, ...]


class BrokeredAdmissionSearchEngine(RideHailingSearchEngine):
    """
    A RideHailingSearchEngine that asks the decision broker before it offers the vehicles it found.

    Select it in the ``operators.py`` of the project through ``SEARCH_ENGINE_TYPE``.
    Each search that finds at least one alternative calls ``decide`` with the uid of the operator and a ``Search`` payload.
    A True reply offers the alternatives.
    A False reply defers the request: the search returns no alternatives.
    A missing broker offers.

    Parameters
    ----------
    deps : SearchEngineDependencies
        Standard search engine dependencies.
    """

    def __init__(self, deps: SearchEngineDependencies) -> None:
        super().__init__(deps)
        self._broker = deps.sim.decision_broker
        if self._broker is None:
            self.logger.warning(
                "No decision broker attached. %s offers every request the vehicles it finds.",
                type(self).__name__,
            )

    def search_for_transportation_alternatives(
        self, transport_task: TransportRequest
    ) -> TransportationAlternativeBrowser:
        """Search as the plain engine does, then ask the broker whether to offer the result.

        Parameters
        ----------
        transport_task : TransportRequest
            Transport demand to serve.

        Returns
        -------
        TransportationAlternativeBrowser
            Alternatives as found, or none when the request is deferred.

        Raises
        ------
        TypeError
            If the reply is not a bool.
        """
        browser = super().search_for_transportation_alternatives(transport_task)
        alternatives = browser.transportation_alternatives
        if self._broker is None or not alternatives:
            return browser
        search = Search(transport_task, tuple(alternatives))
        if _offers(self._broker.decide(self.operator.uid, search)):
            return browser
        return TransportationAlternativeBrowser()


def _offers(reply: object) -> bool:
    """Return the reply as the offer flag: True offers the alternatives, False defers."""
    if not isinstance(reply, bool):
        msg = (
            "Expected True to offer or False to defer as the reply, "
            f"got {type(reply).__name__}."
        )
        raise TypeError(msg)
    return reply
