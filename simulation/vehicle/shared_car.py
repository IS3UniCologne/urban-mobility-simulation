from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedCar(SharedVehicle):

    # Shared Care Counter
    shared_car_id = 0

    def __init__(self, env: Environment, position, max_available_seats = 4, velocity = 166.7):
        super(SharedCar, self).__init__(env, position, max_available_seats, velocity)

        # Increment Shared Car ID
        self.car_id = SharedCar.shared_car_id
        SharedCar.shared_car_id += 1


