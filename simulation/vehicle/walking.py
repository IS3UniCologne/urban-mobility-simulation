from simpy import Environment
import logging
from typing import Any
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.infrastructure.network.edge import Edge
from simulation.vehicle.vehicle import Vehicle


### Basically a singleton that is used as a placeholder in the vehicle slot for search and allocations signifying that a user is walking this route.
class Walking(Vehicle):
    walking_id = 0

    def __init__(self, env: Environment, velocity: float =83.33) -> None:
        # Position of Walking actually just takes user position, so it does not matter
        super(Walking, self).__init__(env, GeodesicPosition(0, 0, None))

        self._id: int = Walking.walking_id
        self._velocity: float = velocity

    @property
    def id(self) -> int:
        return self._id

    @property
    def velocity(self) -> float:
        return self._velocity

    def move(self, route_segment: Edge):
        logging.warning(
            "Warning: Method 'move' for walking called, even though it is not implemented!",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

    def __str__(self) -> str:
        return "I am walking!"
