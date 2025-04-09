from typing import List

from simulation.infrastructure.charging_stations.charging_station import ChargingStation
from tracking.tracking import Tracking


class ChargingInfrastructure:
    __instance = None

    __slots__ = (
        "_env",
        "_location_list",
        "_power_list",
        "_capacity_list",
        "_queue_size",
        "_charging_stations",
        "_tracking",
    )

    @staticmethod
    def instance() -> "ChargingInfrastructure":
        """Static access method."""
        if ChargingInfrastructure.__instance is None:
            raise Exception("ChargingInfrastructure was not initialized")
        else:
            return ChargingInfrastructure.__instance

    @staticmethod
    def init(
        env,
        location_list: List[str],
        power_list: List[float],
        capacity_list: List[int],
        queue_size: List[int],
        reset=False,
    ):
        """Static access method."""
        if ChargingInfrastructure.__instance is None or reset is True:
            ChargingInfrastructure(
                env, location_list, power_list, capacity_list, queue_size, reset
            )
        return ChargingInfrastructure.__instance

    def __init__(
        self,
        env,
        location_list: List[str],
        power_list: List[float],
        capacity_list: List[int],
        queue_size: List[int],
        reset: bool = False,
    ):
        """Virtually private constructor."""
        if ChargingInfrastructure.__instance is not None and not reset:
            raise Exception("This class is a singleton!")
        else:
            ChargingInfrastructure.__instance = self
            super(ChargingInfrastructure, self).__init__()
        self._env = env
        self._tracking = Tracking.instance()
        self._location_list = location_list
        self._power_list = power_list
        self._capacity_list = capacity_list
        self._queue_size = queue_size
        self._charging_stations = []  # a list of charger objects
        self._initialise_charging_stations()

    def _initialise_charging_stations(self):
        for i, location in enumerate(self._location_list):
            charging_station = ChargingStation(
                id=i,
                env=self._env,
                location=location,
                power=self._power_list[i],
                capacity=self._capacity_list[i],
                queue_size=self._queue_size[i],
            )
            self._charging_stations.append(charging_station)
            self._tracking.register(charging_station)

    @property
    def charging_stations(self):
        return self._charging_stations

    def get_locations(self):
        return self._location_list
