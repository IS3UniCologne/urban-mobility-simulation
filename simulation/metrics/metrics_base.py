"""Base classes for metrics."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import logging

    from simulation.helper.types import SimId
    from simulation.simulation import Simulation

    from .metrics_dict import MetricsDict


class MetricsBase(ABC):
    """
    Abstract base class for all user-facing metrics classes.

    Provides a standard interface for metrics access and logging.

    Parameters
    ----------
    simulation : Simulation
        The main simulation instance.
    """

    def __init__(self, simulation: Simulation) -> None:
        self._simulation: Simulation = simulation

    @abstractmethod
    def to_dict(self) -> MetricsDict:
        """
        Return all available metrics for this class.

        Returns
        -------
        MetricsDict
            Dictionary containing all metrics.
        """
        pass

    def to_log(self, logger: logging.Logger | None = None) -> None:
        """
        Output metrics to the log.

        Wraps around the MetricsDict's to_log method.

        Parameters
        ----------
        logger : logging.Logger or None
            Logger to use for output. If None, uses the root logger.
        """
        metrics_dict = self.to_dict()
        metrics_dict.to_log(logger)


class IndexedMetricsBase(MetricsBase):
    """
    Base class for indexed metrics (e.g. operator-specific metrics).

    Extends MetricsBase to provide UID-based access.
    """

    @abstractmethod
    def get_metrics_by_uid(self, uid: SimId) -> MetricsDict:
        """
        Get metrics for a specific entity by UID.

        Parameters
        ----------
        uid : SimId
            The unique identifier of the entity as defined in SimulationBase.

        Returns
        -------
        MetricsDict
            Dictionary containing metrics for the specified entity.

        Raises
        ------
        KeyError
            If the entity ID is not found.
        """
        pass

    @abstractmethod
    def list_available_uids(self) -> list[SimId]:
        """
        Get list of all available entity UIDs.

        Returns
        -------
        list of SimId
            List of available entity UIDs.
        """
        pass

    def __getitem__(self, entity_id: SimId) -> MetricsDict:
        """
        Get metrics for a specific entity by UID using indexing syntax (e.g. OperatorMetrics["Operator_1"]).

        Parameters
        ----------
        entity_id : str
            The unique identifier of the entity.

        Returns
        -------
        MetricsDict
            Dictionary containing metrics for the specified entity.

        Raises
        ------
        KeyError
            If the entity UID is not found.
        """
        return self.get_metrics_by_uid(entity_id)
