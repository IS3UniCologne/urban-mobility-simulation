from typing import TYPE_CHECKING
from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition

class SharedKickScooter(SharedVehicle):
    # Shared Kick Scooter Counter
    shared_kick_scooter_id:int = 0
    vehicle_type:str = "shared_kick_scooter"

    def __init__(
        self,
        env: Environment,
        position: "GeodesicPosition",
        velocity: float,
        max_available_seats: int=1,
        max_state_of_charge: float=0.288,
        energy_consumption: float=0.0072,
        price_per_min: float=0.19,
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
        self._shared_kick_scooter_id:int = SharedKickScooter.shared_kick_scooter_id
        SharedKickScooter.shared_kick_scooter_id += 1
