from collections.abc import Generator  # noqa: D100

from simpy import Environment, Event

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.infrastructure.network.edge import Edge
from simulation.vehicle.movement_stats import MovementStats
from simulation.vehicle.vehicle import Vehicle


# TODO: We should probably delete this.
### Basically a singleton that is used as a placeholder in the vehicle slot for search and allocations signifying that a user is walking this route.
class Walking(Vehicle):  # noqa: D101
    __slots__ = ("_id", "_velocity")

    def __init__(self, env: Environment, velocity: float = 83.33) -> None:
        # Position of Walking actually just takes user position, so it does not matter
        super(Walking, self).__init__(env, GeodesicPosition(0, 0, None))  # noqa: UP008

        self._velocity_mm = velocity

    @property
    def velocity(self) -> float:  # noqa: D102
        return self._velocity_mm

    def _move(self, route_segment: Edge) -> Generator[Event, None, MovementStats]:
        self.logger.warning(
            "Warning: Method 'move' for walking called, even though it is not implemented!"
        )

        if False:
            yield self._env.timeout(0)
        return MovementStats(0, 0, 0)

    def __str__(self) -> str:  # noqa: D105
        return "I am walking!"
