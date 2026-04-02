"""User logging module.

This module logs user trip requests and their outcomes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from simulation.helper.simulation_base import SimulationBase
from simulation.metrics.statistics.user_log_stats import UserLogStats

if TYPE_CHECKING:
    from simulation.agent.user.user_log import UserLogEntry
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.interface.operator_interface import OperatorInterface


class UserLog(SimulationBase):
    """
    log for user trip requests and outcomes.

    This class tracks all user trip requests in the simulation and their final outcomes,
    independent of operator-specific transaction logs. This provides accurate
    system-level metrics without double-counting failed allocation attempts.

    Similar to how operators have OperatorLog for their services, the UserLog
    tracks trip requests from the user/demand perspective.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    max_window_size : int, optional
        Maximum size of the recent outcomes window. Default is 1440.

    Attributes
    ----------
    metrics : UserLogStats
        Metrics tracker for user logs.
    """

    __slots__ = ("_env", "_sim", "_user_trip_outcomes", "metrics")

    def __init__(self, sim: SimulationContext, max_window_size: int = 1440) -> None:
        super().__init__(sim)
        self._sim = sim
        self._env = sim.env
        self._user_trip_outcomes: list[UserLogEntry] = []
        self.metrics = UserLogStats(recent_window_size=max_window_size)

    def log_trip_outcome(self, outcome: UserLogEntry) -> None:
        """
        Log the final outcome of a user's trip request.

        Parameters
        ----------
        outcome : UserLogEntry
            The user trip outcome to log.
        """
        self._user_trip_outcomes.append(outcome)

        # Update incremental metrics
        self.metrics.on_outcome(outcome)

        self.logger.debug(
            "User trip outcome logged for user %s: %s",
            outcome.user_uid,
            outcome.outcome_state.value,
        )

    @property
    def user_trip_outcomes(self) -> list[UserLogEntry]:
        """Get all user trip outcomes."""
        return self._user_trip_outcomes

    @property
    def total_trip_requests(self) -> int:
        """Get total number of trip requests."""
        return self.metrics.total

    @property
    def total_fulfilled_trips(self) -> int:
        """Get total number of successfully fulfilled trips."""
        return self.metrics.fulfilled

    @property
    def total_missed_trips(self) -> int:
        """Get total number of missed trips."""
        return self.metrics.missed

    @property
    def fulfillment_rate(self) -> float:
        """Get the overall trip fulfillment rate."""
        if self.metrics.total == 0:
            return 0.0
        return self.metrics.fulfilled / self.metrics.total

    def get_operator_stats(self, operator: OperatorInterface) -> dict[str, float]:
        """
        Get statistics for a specific operator from system-level view.

        Parameters
        ----------
        operator : OperatorInterface
            The operator to get stats for.

        Returns
        -------
        dict[str, float]
            Dictionary containing 'fulfilled', 'attempted', and 'success_rate'.
        """
        stats = self.metrics.get_operator_stats(operator.uid)
        # Convert to float for compatibility if needed, though get_operator_stats returns int|float
        return {
            "fulfilled": float(stats["fulfilled"]),
            "attempted": float(stats["attempted"]),
            "success_rate": float(stats["success_rate"]),
        }

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert user trip outcomes to a pandas DataFrame.

        Returns
        -------
        pd.DataFrame
            DataFrame containing all user trip outcomes.
        """
        if not self._user_trip_outcomes:
            return pd.DataFrame()

        data = [outcome.to_dict() for outcome in self._user_trip_outcomes]
        df = pd.DataFrame(data)
        df["num_operators_attempted"] = df["attempted_operator_uids"].apply(len)
        return df

    def get_fulfillment_rate_recent(self) -> float:
        """
        Get fulfillment rate for recent trip outcomes only.

        Returns
        -------
        float
            Ratio of fulfilled trips to total trips in the recent window.
        """
        return self.metrics.fulfillment_rate_recent
