from simulation.infrastructure.charging_stations.charging_infastructure import ChargingInfrastructure
from simulation.operator.operations_management.refueling_strategy import RefuelingStrategy
from simulation.operator.operations_management.relocation_strategy import RelocationStrategy
from simulation.operator.operator import Operator
from simulation.operator.service_workforce import ServiceWorkforce
from simulation.operator.vehicle_fleet import VehicleFleet

class SharedMobiltyOperator(Operator):

    def __init__(self, fleet: VehicleFleet, charging_infrastructure: ChargingInfrastructure, refueling_strategy: RefuelingStrategy, relocation_strategy: RelocationStrategy, number_service_workers: int):
        super(SharedMobiltyOperator, self).__init__(fleet, charging_infrastructure, refueling_strategy, relocation_strategy)
        
        self._service_workforce = ServiceWorkforce(env=self.env, number_service_workers=number_service_workers)

        #TODO: enforce that used strategies are SharedMobilityStrategy

        refueling_strategy.register_workforce(self._service_workforce)
        relocation_strategy.register_workforce(self._service_workforce)