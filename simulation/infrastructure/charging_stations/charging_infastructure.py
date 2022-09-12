from simulation.infrastructure.charging_stations.charging_station import ChargingStation


class ChargingInfrastructure:
    __instance = None

    @staticmethod
    def instance() -> 'ChargingInfrastructure':
        """ Static access method. """
        if ChargingInfrastructure.__instance is None:
            raise Exception("ChargingInfrastructure was not initialized")
        else:
            return ChargingInfrastructure.__instance

    @staticmethod
    def init(env, location_list, power_list, capacity_list,
             reset=False):
        """ Static access method. """
        if ChargingInfrastructure.__instance is None or reset is True:
            ChargingInfrastructure(env, location_list, power_list, capacity_list, reset)
        return ChargingInfrastructure.__instance

    def __init__(self, env, location_list, power_list, capacity_list, reset: bool = False):
        """ Virtually private constructor. """
        if ChargingInfrastructure.__instance is not None and not reset:
            raise Exception("This class is a singleton!")
        else:
            ChargingInfrastructure.__instance = self
            super(ChargingInfrastructure, self).__init__()
        self.env = env
        self.location_list = location_list
        self.power_list = power_list
        self.capacity_list = capacity_list
        self._chargers = []  # a list of charger objects
        self.initialise_charging_stations()

    def initialise_charging_stations(self):
        for i in range(len(self.location_list)):
            charging_station = ChargingStation(id=i, env=self.env, location=self.location_list[i],
                                               power=self.power_list[i], capacity=self.capacity_list[i])
            self._chargers.append(charging_station)

    @property
    def users(self):
        return self._chargers

