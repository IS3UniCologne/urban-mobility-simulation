from .vehicle import Vehicle
from ..agent.agent import Agent


class SharedVehicle(Vehicle):
    def __init__(self, position,  max_available_seats = 1):
        super(SharedVehicle, self).__init__(position, max_available_seats, max_available_seats)

    def start_driving(self):
        pass

    def stop_driving(self):
        pass

    def __str__(self):
        return f'I have {len(self._seats)} passengers on boards'