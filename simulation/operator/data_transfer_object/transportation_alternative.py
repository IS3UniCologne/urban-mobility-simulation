"""
Data transfer object for transportation alternatives.

Represents a potential trip option with estimated properties.
"""

from simulation.infrastructure.route import Route
from simulation.vehicle.vehicle import Vehicle

# Todo: turn this back into a dataclass once we do the user refactoring (and move waiting time and energy consumed into trip records)
# @dataclass(frozen=True, slots=True)
# class TransportationAlternative:
#     """
#     Represents a potential transportation alternative.

#     Parameters
#     ----------
#     vehicle : Vehicle
#         The vehicle associated with this alternative.
#     route : Route
#         The route for this alternative.
#     price : float
#         The price of the trip.
#     duration : float
#         The estimated duration of the trip.
#     distance : float
#         The estimated distance of the trip.
#     convenience : float
#         The convenience score (lower is better).
#     """

#     vehicle: Vehicle
#     route: Route
#     price: float
#     duration: float
#     distance: float
#     convenience: float

#     def __str__(self) -> str:
#         return (
#             f"Vehicle {self.vehicle}, Price {self.price}, Duration {self.duration}, "
#             f"Distance {self.distance}, Convenience {self.convenience}"
#         )

#     def __repr__(self) -> str:
#         return self.__str__()


class TransportationAlternative:  # noqa: D101
    __slots__ = (
        "_autonomous_vehicle",
        "_convenience",
        "_distance",
        "_distance_to_pickup",
        "_duration",
        "_energy_consumed",
        "_pick_up_time",
        "_price",
        "_route",
        "_route_to_pickup",
        "_utility",
        "_vehicle",
        "_waiting_time",
    )

    def __init__(
        self,
        vehicle: Vehicle,
        route: Route,
        price: float,
        duration: float,
        distance: float,
        convenience: float,
        route_to_pickup: Route | None = None,
        pick_up_time: float | None = None,
    ) -> None:
        self._vehicle = vehicle
        self._price = price
        self._duration = duration
        self._distance = distance
        self._route = route
        self._convenience = convenience  # the ranking (the lower, the better)
        self._route_to_pickup = route_to_pickup
        self._pick_up_time = pick_up_time
        self._utility = 0.0
        self._waiting_time = 0.0  # Is set after successful allocation
        self._energy_consumed = 0.0  # Is set after successful trip

    @property
    def utility(self) -> float:  # noqa: D102
        return self._utility

    @utility.setter
    def utility(self, utility: float) -> None:
        self._utility = utility

    @property
    def vehicle(self) -> Vehicle:  # noqa: D102
        return self._vehicle

    @property
    def price(self) -> float:  # noqa: D102
        return self._price

    @property
    def duration(self) -> float:  # noqa: D102
        return self._duration

    @property
    def distance(self) -> float:  # noqa: D102
        return self._distance

    @property
    def route(self) -> Route:  # noqa: D102
        return self._route

    @property
    def convenience(self) -> float:  # noqa: D102
        return self._convenience

    @property
    def route_to_pickup(self) -> Route | None:  # noqa: D102
        return self._route_to_pickup

    @property
    def pick_up_time(self) -> float | None:  # noqa: D102
        return self._pick_up_time

    # Perhaps it makes sense to encapsulate TransportationAlternative
    #  around a "SuccessfulTrip" where we store this object along with
    #  variables pertaining the to trip (as energy consumed, (real) travelled distance)
    @property
    def energy_consumed(self) -> float:  # noqa: D102
        return self._energy_consumed

    def increase_energy_consumed(self, energy_consumption: float) -> None:  # noqa: D102
        # energy_consumption: in kWh
        self._energy_consumed += energy_consumption

    @property
    def waiting_time(self) -> float:  # noqa: D102
        return self._waiting_time

    def increase_waiting_time(self, waiting_time: float) -> None:  # noqa: D102
        self._waiting_time += waiting_time

    def __str__(self) -> str:  # noqa: D105
        return f"Vehicle {self._vehicle}, Price {self._price}, Duration {self._duration}, Distance {self._distance}, Convenience {self._convenience} {', Distance to pickup ' + str(self._route_to_pickup.distance) + ', Pick up time ' + str(self._pick_up_time) if self._route_to_pickup else ''},"

    def __repr__(self) -> str:  # noqa: D105
        return self.__str__()
