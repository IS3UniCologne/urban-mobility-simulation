"""Mobility as a Service (MaaS) provider for aggregating transportation alternatives from multiple operators.

TODO: Will be developed in the following stages:

        # Stage 1: Offer alternatives from all operators (just act as a SearchEngine aggregator)
        # Stage 2: Add filtering based on user preferences
        # Stage 3: Implement (delayed) vehicle allocation
        # Stage 4: Implement composite trips (e.g., shared vehicle + public transit)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase
from simulation.operator.interface.search_engine_interface import SearchEngineInterface

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.data_transfer_object.transportation_alternative_browser import (
        TransportationAlternativeBrowser,
    )
    from simulation.operator.interface.operator_interface import OperatorInterface
    from simulation.tasks.transportation_search_task import TransportationSearchTask

from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)


class MaaSProvider(SimulationBase, SearchEngineInterface):
    """Provides aggregated transport alternative search across all registered operators."""

    def __init__(
        self, sim: SimulationContext, operators: list[OperatorInterface] | None = None
    ) -> None:
        super().__init__(sim)
        self._operators: list[OperatorInterface] = operators or []

    def register_operator(self, operator: OperatorInterface) -> None:
        """Register an operator to the MaaS provider.

        Parameters
        ----------
        operator : OperatorInterface
            The operator to register.
        """
        self._operators.append(operator)

    def search_for_transportation_alternatives(
        self, vehicle_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        """Search for transportation alternatives across all registered operators.

        Parameters
        ----------
        vehicle_search_task : TransportationSearchTask
            The task containing search parameters.
        """
        aggregated = TransportationAlternativeBrowser()
        """
        Aggregates transportation alternatives from all registered operators."""

        for operator in self._operators:
            alternatives: TransportationAlternativeBrowser = (
                operator.search_engine.search_for_transportation_alternatives(
                    vehicle_search_task
                )
            )
            # TODO: This is a very stupid way to aggregate. We have to refactor this later.
            for alt in alternatives.transportation_alternatives:
                aggregated.add_transportation_alternative(alt)

        return aggregated
