from simpy import Environment

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.vehicle.vehicle import Vehicle
 

### Basically a singleton that is used as a placeholder in the vehicle slot for search and allocations signifying that a user is walking this route.
class Walking(Vehicle):
    walking_id = 0

    def __init__(
        self, env: Environment, velocity = 83.33
    ):
        # Position of Walking actually just takes user position, so it does not matter
        super(Walking, self).__init__(env, GeodesicPosition(0, 0, None))

        self._id = Walking.walking_id
        self._velocity = velocity

    @property
    def id(self):
        return self._id

    @property
    def velocity(self):
        return self._velocity

    def move(self, route_segment):
        pass

    def __str__(self):
        return "I am walking!"
