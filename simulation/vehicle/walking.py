from simpy import Environment
import logging

from simulation.vehicle.vehicle import Vehicle, VehicleState
from simulation.environment.position import Position
from simulation.infrastructure.network.edge import Edge
from simulation.vehicle.interfaces.driver_interface import DriverInterface
 

### Basically a singleton that is used as a placeholder in the vehicle slot for search and allocations signifying that a user is walking this route.
class Walking(Vehicle):
    walking_id = 0

    def __init__(self, env: Environment, position, velocity = 83.33, driver: DriverInterface = None):
        super(Walking, self).__init__(env, position)

        self._id = Walking.walking_id
        self._velocity = velocity

    @property
    def id(self):
        return self._id
    
    @property
    def velocity(self):
        return self._velocity

    def move(self, route_segment: Edge):
        pass
        
    def __str__(self):
        return f'I am walking!'