from typing import TYPE_CHECKING
from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle


if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition

class SharedBike(SharedVehicle):
    # Shared Bike Counter
    shared_bike_id: int = 0

    def __init__(
        self,
        env: Environment,
        position: "GeodesicPosition",
        velocity: float,
        max_available_seats: int=1,
        max_state_of_charge: int=0,
        price_per_min: float=0.08,
    ):
        """

        :param env:
        :param position:
        :param max_available_seats:
        (see e.g, https://www.okai.co/products/es200) vendor of Tier (8aH, 36V => 288Wh)
        :param velocity:
        """
        super(SharedBike, self).__init__(
            env,
            position,
            velocity,
            max_available_seats,
            max_state_of_charge,
            0.0,
            price_per_min,
        )

        # Increment Shared Car ID
        self._shared_bike_id: int = SharedBike.shared_bike_id

        SharedBike.shared_bike_id += 1

    def _update_state_of_charge(self, distance: int) -> None:
        pass

    def has_enough_state_of_charge(self, distance:int) -> bool:
        return True
