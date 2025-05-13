from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle


class SharedKickScooter(SharedVehicle):
    # Shared Kick Scooter Counter
    shared_kick_scooter_id = 0
    vehicle_type = "shared_kick_scooter"

    __slots__ = (
        "_velocity",
        "_max_available_seats",
        "_max_state_of_charge",
        "_energy_consumption",
        "_price_per_minute",
        "_shared_kick_scooter_id",
    )

    def __init__(
        self,
        env: Environment,
        position,
        velocity,
        max_available_seats=1,
        max_state_of_charge=0.288,
        energy_consumption=0.0072,
        price_per_min=0.19,
    ):
        """

        :param env:
        :param position:
        :param max_available_seats:
        :param max_state_of_charge:
        :param energy_consumption:
        (see e.g, https://www.okai.co/products/es200) vendor of Tier (8aH, 36V => 288Wh)
        :param velocity:
        """
        super(SharedKickScooter, self).__init__(
            env,
            position,
            velocity,
            max_available_seats,
            max_state_of_charge,
            energy_consumption,
            price_per_min,
        )

        # Increment Shared Car ID
        self._shared_kick_scooter_id = SharedKickScooter.shared_kick_scooter_id
        SharedKickScooter.shared_kick_scooter_id += 1
