from typing import TYPE_CHECKING  # noqa: D100

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.time import SimulationTime
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.vehicle.vehicle import Vehicle

if TYPE_CHECKING:
    from simulation.agent.user import User


class VehicleAllocation:  # noqa: D101
    __slots__ = (
        "_energy_consumed",
        "_pick_up_position",
        "_pick_up_time",
        "_transportation_alternative",
        "_user",
        "_vehicle",
    )

    def __init__(  # noqa: ANN204
        self,
        user: "User",
        transportation_alternative: TransportationAlternative,
        pick_up_position: GeodesicPosition,
        pick_up_time: SimulationTime,
    ):
        self._user = user  # User that got the assignment
        self._vehicle = (
            transportation_alternative.vehicle
        )  # Vehicle that got assigned to above user
        self._transportation_alternative = (
            transportation_alternative  # Selected transportation offer
        )
        self._pick_up_position = (
            pick_up_position  # Pick up position of user for vehicle
        )
        self._pick_up_time = pick_up_time  # Pick up time (i.e., when will be the vehicle be at pickup pos)
        self._energy_consumed = 0.0

    @property
    def user(self) -> "User":  # noqa: D102
        return self._user

    @property
    def vehicle(self) -> Vehicle:  # noqa: D102
        return self._vehicle

    @property
    def transportation_alternative(self) -> TransportationAlternative:  # noqa: D102
        return self._transportation_alternative

    @property
    def pick_up_position(self) -> GeodesicPosition:  # noqa: D102
        return self._pick_up_position

    @property
    def pick_up_time(self) -> SimulationTime:  # noqa: D102
        return self._pick_up_time

    @property
    def energy_consumed(self) -> float:
        """Get the energy consumed during the allocation (pickup + trip)."""
        return self._energy_consumed

    @energy_consumed.setter
    def energy_consumed(self, value: float) -> None:
        self._energy_consumed = value

    def increase_energy_consumed(self, amount: float) -> None:
        """Increase the energy consumed by the given amount."""
        self._energy_consumed += amount
