from simulation.infrastructure.route import Route
from simulation.vehicle.vehicle import Vehicle


class TransportationAlternative:
    __slots__ = (
        "_convenience",
        "_distance",
        "_duration",
        "_energy_consumed",
        "_price",
        "_route",
        "_vehicle",
        "_waiting_time",
    )

    def __init__(  # noqa: ANN204
        self,
        vehicle: Vehicle,
        route: Route,
        price,  # noqa: ANN001
        duration,  # noqa: ANN001
        distance,  # noqa: ANN001
        convenience,  # noqa: ANN001
    ):
        self._vehicle = vehicle
        self._price = price
        self._duration = duration
        self._distance = distance
        self._route = route
        self._convenience = convenience  # the ranking (the lower, the better)

        self._energy_consumed = 0.0  # Is set after successful trip
        self._waiting_time = 0

    @property
    def vehicle(self):  # noqa: ANN201
        return self._vehicle

    @property
    def price(self):  # noqa: ANN201
        return self._price

    @property
    def duration(self):  # noqa: ANN201
        return self._duration

    @property
    def distance(self):  # noqa: ANN201
        return self._distance

    @property
    def route(self):  # noqa: ANN201
        return self._route

    @property
    def convenience(self):  # noqa: ANN201
        return self._convenience

    @property
    def waiting_time(self):  # noqa: ANN201
        return self._waiting_time

    # Perhaps it makes sense to encapsulate TransportationAlternative
    #  around a "SuccessfulTrip" where we store this object along with
    #  variables pertaining the to trip (as energy consumed, (real) travelled distance)
    @property
    def energy_consumed(self):  # noqa: ANN201
        return self._energy_consumed

    def set_energy_consumed(self, energy_consumption):  # noqa: ANN001, ANN201
        # energy_consumption: in kWh
        self._energy_consumed = energy_consumption

    def __str__(self) -> str:
        return f"Vehicle {self._vehicle}, Price {self._price}, Duration {self._duration}, Distance {self._distance}, Convenience {self._convenience}"
