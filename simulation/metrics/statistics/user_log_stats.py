"""Incremental stats tracker for UserLog."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from simulation.agent.user.user_log.user_log_entry import (
    FulfilledUserLogEntry,
    UserLogEntry,
)
from simulation.helper.enums import TransactionState

if TYPE_CHECKING:
    from simulation.helper.types import SimId


class UserLogStats:
    """
    Stats tracker for UserLog.

    Incrementally updates with every new outcome to provide O(1) access to common statistics.

    Parameters
    ----------
    recent_window_size : int, optional
        Maximum size of the recent outcomes window. Default is 1440.

    Attributes
    ----------
    attempted_per_op : dict of SimId to int
        Count of attempted trips per operator.
    fulfilled : int
        Total number of fulfilled trips.
    fulfilled_per_op : dict of SimId to int
        Count of fulfilled trips per operator.
    missed : int
        Total number of missed trips.
    total : int
        Total number of trip requests.
    total_energy_consumed : float
        Total energy consumed by all fulfilled trips.
    total_revenue : float
        Total revenue paid by users.
    total_search_time : float
        Total time spent searching for trips.
    total_trip_duration : float
        Total duration of all fulfilled trips.
    total_wait_time : float
        Total wait time for all fulfilled trips.
    """

    __slots__ = (
        "_recent_outcomes",
        "attempted_per_op",
        "fulfilled",
        "fulfilled_per_op",
        "missed",
        "total",
        "total_energy_consumed",
        "total_revenue",
        "total_search_time",
        "total_trip_duration",
        "total_wait_time",
    )

    def __init__(self, recent_window_size: int = 1440) -> None:
        self.total = 0
        self.fulfilled = 0
        self.missed = 0
        self.attempted_per_op: dict[SimId, int] = {}
        self.fulfilled_per_op: dict[SimId, int] = {}
        self.total_revenue = 0.0
        self.total_search_time = 0.0
        self.total_wait_time = 0.0
        self.total_trip_duration = 0.0
        self.total_energy_consumed = 0.0
        # TODO: Make recent_window_size configurable ? Make it the default in all incremental metrics?
        self._recent_outcomes: deque[UserLogEntry] = deque(maxlen=recent_window_size)

    def on_outcome(self, outcome: UserLogEntry) -> None:
        """
        Update incremental metrics based on a new outcome.

        Parameters
        ----------
        outcome : UserLogEntry
            The user trip outcome to process.
        """
        self.total += 1
        self.total_search_time += outcome.search_duration
        self._recent_outcomes.append(outcome)

        if isinstance(outcome, FulfilledUserLogEntry):
            self.fulfilled += 1
            if outcome.fulfilled_by_operator_uid is not None:
                self.fulfilled_per_op[outcome.fulfilled_by_operator_uid] = (
                    self.fulfilled_per_op.get(outcome.fulfilled_by_operator_uid, 0) + 1
                )

            if outcome.price_paid is not None:
                self.total_revenue += outcome.price_paid
            if outcome.actual_wait_time is not None:
                self.total_wait_time += outcome.actual_wait_time
            if outcome.trip_duration is not None:
                self.total_trip_duration += outcome.trip_duration
            if outcome.energy_consumed is not None:
                self.total_energy_consumed += outcome.energy_consumed
        else:
            self.missed += 1

        for op_uid in outcome.attempted_operator_uids:
            self.attempted_per_op[op_uid] = self.attempted_per_op.get(op_uid, 0) + 1

    @property
    def total_trip_requests(self) -> int:
        """Get total number of trip requests."""
        return self.total

    @property
    def total_fulfilled_trips(self) -> int:
        """Get total number of fulfilled trips."""
        return self.fulfilled

    @property
    def total_missed_trips(self) -> int:
        """Get total number of missed trips."""
        return self.missed

    @property
    def fulfillment_rate(self) -> float:
        """Calculate trip fulfillment rate."""
        if self.total == 0:
            return 0.0
        return self.fulfilled / self.total

    @property
    def fulfillment_rate_recent(self) -> float:
        """
        Calculate trip fulfillment rate for recent trips only.

        Returns
        -------
        float
            Ratio of fulfilled trips to total trips in the recent window.
        """
        if not self._recent_outcomes:
            return 0.0
        fulfilled = sum(
            1
            for outcome in self._recent_outcomes
            if outcome.outcome_state == TransactionState.FULFILLED
        )
        return fulfilled / len(self._recent_outcomes)

    @property
    def average_price_paid(self) -> float:
        """Calculate average price paid for fulfilled trips."""
        if self.fulfilled == 0:
            return 0.0
        return self.total_revenue / self.fulfilled

    @property
    def average_search_time(self) -> float:
        """Calculate average search time per user."""
        if self.total == 0:
            return 0.0
        return self.total_search_time / self.total

    @property
    def average_wait_time(self) -> float:
        """Calculate average wait time for fulfilled trips."""
        if self.fulfilled == 0:
            return 0.0
        return self.total_wait_time / self.fulfilled

    @property
    def average_trip_duration(self) -> float:
        """Calculate average trip duration for fulfilled trips."""
        if self.fulfilled == 0:
            return 0.0
        return self.total_trip_duration / self.fulfilled

    @property
    def average_energy_consumed(self) -> float:
        """Calculate average energy consumed per fulfilled trip."""
        if self.fulfilled == 0:
            return 0.0
        return self.total_energy_consumed / self.fulfilled

    def get_operator_stats(self, operator_uid: SimId) -> dict[str, int | float]:
        """
        Get statistics for a specific operator from the user's perspective.

        Parameters
        ----------
        operator_uid : SimId
            The operator UID to get stats for.

        Returns
        -------
        dict[str, int | float]
            Dictionary containing 'fulfilled', 'attempted', 'success_rate', and 'market_share'.
        """
        fulfilled = self.fulfilled_per_op.get(operator_uid, 0)
        attempted = self.attempted_per_op.get(operator_uid, 0)
        success_rate = (fulfilled / attempted) if attempted > 0 else 0.0
        total_fulfilled = self.fulfilled
        market_share = (fulfilled / total_fulfilled) if total_fulfilled > 0 else 0.0

        return {
            "fulfilled": fulfilled,
            "attempted": attempted,
            "success_rate": success_rate,
            "market_share": market_share,
        }

    def get_all_operator_stats(self) -> dict[SimId, dict[str, int | float]]:
        """
        Get statistics for all operators that have been attempted from the user's perspective.

        Returns
        -------
        dict[SimId, dict[str, int | float]]
            Dictionary mapping operator UIDs to their statistics.
        """
        stats = {}
        operator_uids = set(self.attempted_per_op.keys())
        for op_uid in operator_uids:
            stats[op_uid] = self.get_operator_stats(op_uid)
        return stats
