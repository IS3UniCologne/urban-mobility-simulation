from typing import TYPE_CHECKING
from simpy import Environment

from simulation.vehicle.shared_vehicle import SharedVehicle


if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition

class SharedCar(SharedVehicle):
    # Shared Car Counter
    shared_car_id: int = 0
    vehicle_type: str = "shared_car"

    def __init__(
        self,
        env: Environment,
        position: "GeodesicPosition",
        velocity: float,
        max_available_seats: int=4,
        max_state_of_charge: float=16.7,
        energy_consumption: float=0.152,
        price_per_min: float=0.26,
    ):
        """

        :param env:
        :param position:
        :param max_available_seats: 16.7 kWH as per Smart EQ specification 16.7
        (see e.g.g, https://www.smart.com/de/de/modelle/smart-eq-fortwo-coupe#technische-daten-smart-eq-fortwo-coupe)
        :param max_state_of_charge:
        :param energy_consumption: 15.2 kWh/100km as per Smart EQ specification
        :param velocity:
        """
        super(SharedCar, self).__init__(
            env,
            position,
            velocity,
            max_available_seats,
            max_state_of_charge,
            energy_consumption,
            price_per_min,
        )

        # Increment Shared Car ID
        self.car_id: int = SharedCar.shared_car_id
        self._price_per_minute: int = price_per_min
        SharedCar.shared_car_id += 1
