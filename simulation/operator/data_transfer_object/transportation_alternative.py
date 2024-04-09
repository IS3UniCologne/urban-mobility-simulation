from simulation.infrastructure.route import Route
from simulation.vehicle.vehicle import Vehicle


class TransportationAlternative:
    def __init__(
        self, vehicle: Vehicle, route: Route, price, duration, distance, convenience
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
    def vehicle(self):
        return self._vehicle

    @property
    def price(self):
        return self._price

    @property
    def duration(self):
        return self._duration

    @property
    def distance(self):
        return self._distance

    @property
    def route(self):
        return self._route

    @property
    def convenience(self):
        return self._convenience\

    @property
    def waiting_time(self):
        return self._waiting_time

    # Perhaps it makes sense to encapsulate TransportationAlternative
    #  around a "SuccessfulTrip" where we store this object along with
    #  variables pertaining the to trip (as energy consumed, (real) travelled distance)
    @property
    def energy_consumed(self):
        return self._energy_consumed

    def set_energy_consumed(self, energy_consumption):
        # energy_consumption: in kWh
        self._energy_consumed = energy_consumption
