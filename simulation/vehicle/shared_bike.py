from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle
from simulation.environment.geodesic_position import GeodesicPosition

class SharedBike(SharedVehicle):
    # Shared Bike Counter
    shared_bike_id = 0

    def __init__(self, env: Environment, position: GeodesicPosition, energy_consumption = 0.0, velocity = 333.33, price_per_min = 1/30):
        super(SharedBike, self).__init__(env = env, position = position, energy_consumption = energy_consumption, velocity = velocity, price_per_min = price_per_min)

        # Increment Shared Bike ID
        self._shared_bike_id = SharedBike.shared_bike_id
        SharedBike.shared_bike_id += 1
