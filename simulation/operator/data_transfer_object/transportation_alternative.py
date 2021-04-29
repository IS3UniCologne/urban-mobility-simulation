from simulation.infrastructure.route import Route
from simulation.vehicle.vehicle import Vehicle


class TransportationAlternative:

    def __init__(self, vehicle: Vehicle, route: Route, price, duration, distance):
        self._vehicle   = vehicle
        self._price     = price
        self._duration  = duration
        self._distance  = distance
        self._route     = route

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