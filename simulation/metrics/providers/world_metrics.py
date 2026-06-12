"""World metrics module."""

from __future__ import annotations

from time import time
from typing import TYPE_CHECKING

from ..metrics_base import MetricsBase
from ..metrics_dict import MetricsDict

if TYPE_CHECKING:
    from simulation.simulation import Simulation


class WorldMetrics(MetricsBase):
    """
    Metrics class for the simulation world.

    Parameters
    ----------
    simulation : Simulation
        The main simulation instance.
    """

    def __init__(self, simulation: Simulation) -> None:
        super().__init__(simulation)
        self._world = simulation.world
        self._last_evaluation_timestamp = time()

    @property
    def wall_time_per_metric_evaluation(self) -> float:
        """Special metric that clocks simulation walltime.

        Useful for monitoring simulation health.
        Wall time can fluctuate due to various factors like demand generation and periodic operations loops.
        It should, as a general rule of thumb, however, not increase significantly over the course of a simulation run.
        This could indicate problems like accumulating processes or memory leaks.

        Returns
        -------
        float
            The lapsed time in seconds since the last evaluation of this metric.
        """
        now = time()
        timing = now - self._last_evaluation_timestamp
        self._last_evaluation_timestamp = now
        return timing

    @property
    def total_users(self) -> int:
        """Total number of users created so far."""
        return self._world.total_users

    @property
    def total_vehicles(self) -> int:
        """Total number of vehicles in the world."""
        return len(self._world.vehicles)

    @property
    def user_state_distribution(self) -> dict[str, int]:
        # TODO: horribly slow, there should be users by state similar to fleets
        """Distribution of users by their current state."""
        state_counts: dict[str, int] = {}
        for user in self._world.users:
            state_name = (
                user.state.name if hasattr(user.state, "name") else str(user.state)
            )
            state_counts[state_name] = state_counts.get(state_name, 0) + 1
        return state_counts

    @property
    def vehicle_state_distribution(self) -> dict[str, int]:
        """Distribution of vehicles by their current state."""
        state_counts: dict[str, int] = {}
        for op in self._world.operators:
            fleet = op.fleet
            for state, vehicles in fleet.vehicles_by_state.items():
                state_name = state.name if hasattr(state, "name") else str(state)
                state_counts[state_name] = state_counts.get(state_name, 0) + len(
                    vehicles
                )
        return state_counts

    @property
    def active_users(self) -> int:
        """Number of active users."""
        return len(self._world.users)

    def to_dict(self) -> MetricsDict:
        """
        Get all world metrics as a dictionary.

        Returns
        -------
        MetricsDict
            Dictionary containing all world metrics.
        """
        return MetricsDict(
            {
                "total_users": self.total_users,
                "total_vehicles": self.total_vehicles,
                "user_state_distribution": self.user_state_distribution,
                "vehicle_state_distribution": self.vehicle_state_distribution,
                "wall_time_per_metric_evaluation": self.wall_time_per_metric_evaluation,
                "active_users": self.active_users,
            }
        )
