from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedScooter(SharedVehicle):
    # Shared Scooter Counter
    shared_scooter_id = 0
    vehicle_type = "shared_scooter"

    __slots__ = (
        "_velocity",
        "_max_available_seats",
        "_max_state_of_charge",
        "_energy_consumption",
        "_scooter_id",
        "_price_per_minute",
    )

    def __init__(
        self,
        env: Environment,
        position,
        velocity,
        max_available_seats=1,
        max_state_of_charge=4.8,
        energy_consumption=0.01,
        price_per_min=0.23,
    ):
        """

        :param env:
        :param position:
        :param max_available_seats:
        :param max_state_of_charge: 4.8 kWh (2 batteries) as per https://www.govecsgroup.com/modelle/schwalbe/ (model used by emmy)
        :param energy_consumption: 0.048 kWh/km
        :param velocity:
        """
        super(SharedScooter, self).__init__(
            env,
            position,
            velocity,
            max_available_seats,
            max_state_of_charge,
            energy_consumption,
            price_per_min,
        )

        # Increment Shared Car ID
        self._scooter_id = SharedScooter.shared_scooter_id
        self._price_per_minute = price_per_min

        SharedScooter.shared_scooter_id += 1
