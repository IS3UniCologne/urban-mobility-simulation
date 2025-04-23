from typing import TYPE_CHECKING
from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition

class SharedScooter(SharedVehicle):
    # Shared Scooter Counter
    shared_scooter_id:int = 0
    vehicle_type:str = "shared_scooter"

    def __init__(
        self,
        env: Environment,
        position: "GeodesicPosition",
        velocity: float,
        max_available_seats: int=1,
        max_state_of_charge: float=4.8,
        energy_consumption: float=0.01,
        price_per_min: float=0.23,
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
        self._scooter_id:int = SharedScooter.shared_scooter_id
        self._price_per_minute:int = price_per_min

        SharedScooter.shared_scooter_id += 1
