from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedScooter(SharedVehicle):
    # Shared Care Counter
    shared_scooter_id = 0

    def __init__(self, env: Environment, position, max_available_seats=4, velocity=500):
        super(SharedScooter, self).__init__(env, position, max_available_seats, velocity)

        # Increment Shared Car ID
        self.car_id = SharedScooter.shared_scooter_id
        self._price_per_minute = 0.23

        SharedScooter.shared_scooter_id += 1

