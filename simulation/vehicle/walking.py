from simpy import Environment  # noqa: D100

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.infrastructure.network.edge import Edge
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

    def move(self, route_segment: Edge):  # noqa: ANN201, D102
        self.logger.warning(
            "Warning: Method 'move' for walking called, even though it is not implemented!"
        )

    def __str__(self) -> str:  # noqa: D105
        return "I am walking!"
