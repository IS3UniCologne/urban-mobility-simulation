from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedCar(SharedVehicle):

    # Shared Care Counter
    shared_car_id = 0

    def __init__(self, env: Environment, position, max_available_seats = 4, velocity = 833.33):
        super(SharedCar, self).__init__(env, position, max_available_seats, velocity)

        # Increment Shared Car ID
        self.car_id = SharedCar.shared_car_id
        self._price_per_minute = 0.26
        SharedCar.shared_car_id += 1
