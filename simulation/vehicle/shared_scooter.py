from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedScooter(SharedVehicle):
    # Shared Care Counter
    shared_scooter_id = 0

    def __init__(self, env: Environment, position, max_available_seats=4, max_state_of_charge = 4.8, energy_consumption = 0.01, velocity=500):
        """

        :param env:
        :param position:
        :param max_available_seats:
        :param max_state_of_charge: 4.8 kWh (2 batteries) as per https://www.govecsgroup.com/modelle/schwalbe/ (model used by emmy)
        :param energy_consumption: 0.048 kWh/km
        :param velocity:
        """
        super(SharedScooter, self).__init__(env, position, max_available_seats, max_state_of_charge, energy_consumption, velocity)

        # Increment Shared Car ID
        self.car_id = SharedScooter.shared_scooter_id
        self._price_per_minute = 0.23

        SharedScooter.shared_scooter_id += 1

