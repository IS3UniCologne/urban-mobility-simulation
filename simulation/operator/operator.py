from simulation.infrastructure.charging_stations.charging_infastructure import ChargingInfrastructure
from simulation.operator.operations_management.refueling_strategy import RefuelingStrategy
from simulation.operator.operations_management.relocation_strategy import RelocationStrategy
from simulation.operator.vehicle_fleet import VehicleFleet


class Operator:

    def __init__(self, fleet: VehicleFleet, charging_infrastructure: ChargingInfrastructure, refueling_strategy: RefuelingStrategy, relocation_strategy: RelocationStrategy,):
        self._fleet = fleet
        self.charging_infastructure = charging_infrastructure
        self._refueling_operations = refueling_strategy
        self._relocation_operations = relocation_strategy
