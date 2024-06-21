from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)


class VirtualChargingInfrastructure:
    """
    This class provides a virtual charging infrastructure (a special view on the physical charging infrastructure) to a certain observer.
    This could e.g. be fleet operators that are only allowed to charge at locations where they buy capacity.

    This class replicates the API of ChargingInfrastructure.
    """

    def __init__(self, env, observer):
        self._env = env
        self._observer = observer

        self._charging_infrastructure = ChargingInfrastructure.instance()

    def charging_stations(self):
        # TODO: implement
        raise NotImplementedError

    def get_locations(self):
        # TODO: implement
        raise NotImplementedError
