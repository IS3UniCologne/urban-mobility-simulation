from simulation.vehicle.vehicle import Vehicle


class VehicleFleet:
    @property
    def fleet(self):
        return self._fleet.copy()  # to avoid that the fleet can be changed from outside

    def __init__(self, env, capacity):
        self._fleet_capacity = capacity
        self._fleet = []

    def add_vehicle(self, vehicle: Vehicle):
        if vehicle not in self._fleet:
            self._fleet.append(vehicle)
        else:
            raise Exception(f"Vehicle {vehicle} is already registered in Fleet")

    def remove_vehicle(self, vehicle: Vehicle):
        if vehicle in self._fleet:
            self._fleet.remove(vehicle)
        else:
            raise Exception(f"Vehicle {vehicle} is not registered in Fleet yet")
