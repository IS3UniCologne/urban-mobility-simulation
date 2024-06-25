from typing import Dict

from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)


class VirtualChargingInfrastructure:
    """
    This class provides a virtual charging infrastructure (a special view on the physical charging infrastructure) to a certain observer.
    This could e.g. be fleet operators that are only allowed to charge at locations where they buy capacity.

    This class replicates the public API of ChargingInfrastructure.
    """

    __slots__ = ("_env", "_availability", "_charging_infrastructure")

    def __init__(self, env, charging_infrastructure: ChargingInfrastructure):
        self._env = env

        self._availability: Dict[int, Dict[str, int]] = {}

        self._charging_infrastructure = charging_infrastructure

    def charging_stations(self):
        # TODO: implement
        raise NotImplementedError

    def get_available_locations(self, at_timeslot: int):
        all_charging_stations = self._charging_infrastructure.charging_stations
        available_charging_stations = [
            charging_station.location
            for charging_station in all_charging_stations
            if self._availability[at_timeslot].get(charging_station.id, 0) > 0
        ]

        return available_charging_stations

    def get_locations(self):
        """
        Defaults to `get_available_locations() at current time`
        """
        return self._charging_infrastructure.get_available_locations(self._env.now())

    def update(self, timeslot: int, availability: Dict[str, int]):
        self._availability[timeslot] = availability
