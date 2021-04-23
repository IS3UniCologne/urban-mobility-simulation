from enum import Enum
from .vehicle import Vehicle

class SharedVehicleState(Enum):
    PARKING = 0
    DRIVING = 1
    RELOCATING = 2
    CHARGING  = 3

class SharedVehicle(Vehicle):
    def __init__(self, position,  max_available_seats = 1):
        super(SharedVehicle, self).__init__(position, max_available_seats, max_available_seats)

    def start_driving(self):
        self.state = SharedVehicleState.DRIVING
        pass

    def stop_driving(self):
        self.state = SharedVehicleState.PARKING
        pass

    def __str__(self):
        return f'I have {len(self._seats)} passengers on boards'