from simpy import Environment

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.vehicle.vehicle import Vehicle


### Basically a singleton that is used as a placeholder in the vehicle slot for search and allocations signifying that a user is walking this route.
class Walking(Vehicle):
    __slots__ = ("_id", "_velocity")

    def __init__(self, env: Environment, velocity=83.33):  # noqa: ANN001, ANN204
        # Position of Walking actually just takes user position, so it does not matter
        super(Walking, self).__init__(env, GeodesicPosition(0, 0, None))  # noqa: UP008

        self._velocity = velocity

    @property
    def velocity(self):  # noqa: ANN201
        return self._velocity

    def move(self, route_segment):  # noqa: ANN001, ANN201
        self.logger.warning(
            "Warning: Method 'move' for walking called, even though it is not implemented!"
        )

    def __str__(self):  # noqa: ANN204
        return "I am walking!"
