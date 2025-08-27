from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase
from simulation.operator.interface.search_engine_interface import SearchEngineInterface

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import SearchEngineConfig
    from simulation.operator.interface.operator_interface import OperatorInterface


@dataclass(frozen=True, slots=True)
class SearchEngineDependencies:
    """Dependencies required for the SearchEngine.

    This class ensures all subclasses maintain the same init signature.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    config : SearchEngineConfig
        The search engine configuration.
    operator:
    """

    sim: SimulationContext
    config: SearchEngineConfig
    operator: OperatorInterface


class SearchEngine(SimulationBase, SearchEngineInterface):
    def __init__(self, deps: SearchEngineDependencies) -> None:
        super().__init__(deps.sim)
        self._operator = deps.operator
        self._config = deps.config

    @classmethod
    def from_deps(cls, deps: SearchEngineDependencies) -> SearchEngine:
        """Create a SearchEngine instance from dependencies.

        Automatically selects the appropriate search engine implementation based on the configuration.
        """
        search_engine_type = deps.config.SEARCH_ENGINE_TYPE
        return search_engine_type(deps)

    @property
    def operator(self) -> OperatorInterface:
        """The operator associated with this search engine.

        Returns
        -------
        Operator
            The operator instance.
        """
        return self._operator

    @property
    def config(self) -> SearchEngineConfig:
        """The configuration for this search engine.

        Returns
        -------
        SearchEngineConfig
            The search engine configuration.
        """
        return self._config
