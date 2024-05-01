from simpy import Environment

from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.environment.position import Position
from simulation.helper.configuration.configuration import Configuration
from simulation.operator.interface.fleet_interface import FleetInterface
from simulation.vehicle.walking import Walking

### Needed for the FleetInterface in the search engine, basically just represents that a user chooses to walk
class WalkingFleet(FleetInterface):

    def __init__(self, env: Environment):
        super(WalkingFleet, self).__init__(env)
        self._walking = Walking(env, None)
        self.env = env

    @property
    def walking(self):
        return self._walking
    
    def get_all_vehicles(self, region):
        pass

    def get_available_vehicles(self, region):
        pass
