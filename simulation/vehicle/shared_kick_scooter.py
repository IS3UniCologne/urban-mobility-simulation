from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedKickScooter(SharedVehicle):
    # Shared Care Counter
    shared_kick_scooter_id = 0

    def __init__(self, env: Environment, position, max_available_seats=1, velocity=333.33):
        super(SharedKickScooter, self).__init__(env, position, max_available_seats, velocity)

        # Increment Shared Car ID
        self.car_id = SharedKickScooter.shared_kick_scooter_id
        self._price_per_minute = 0.19

        SharedKickScooter.shared_kick_scooter_id += 1
