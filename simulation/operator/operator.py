from simulation.operator.vehicle_fleet import VehicleFleet


class Operator:

    def __init__(self, fleet: VehicleFleet, refueling_operations: RefuelingOperations, relocation_operations: RelocationOperations):
        self._fleet = fleet
        self._refueling_operations = refueling_operations
        self._relocation_operations = relocation_operations
