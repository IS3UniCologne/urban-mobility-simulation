from typing import Dict

from beartype.door import die_if_unbearable
from beartype.roar import BeartypeDoorHintViolation

from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)


class VirtualChargingInfrastructure:
    """
    This class provides a virtual charging infrastructure (a special view on the physical charging infrastructure) to a certain observer.
    This could e.g. be fleet operators that are only allowed to charge at locations where they buy capacity.

    This class replicates the public API of ChargingInfrastructure.
    """

    __slots__ = (
        "_env",
        "_availability",
        "_charging_infrastructure",
        "_virtual_charging_stations",
    )

    def __init__(self, env, charging_infrastructure: ChargingInfrastructure):
        self._env = env

        self._availability: Dict[int, Dict[str, int]] = {}

        self._charging_infrastructure = charging_infrastructure
        self._virtual_charging_stations: Dict[int, Dict[str, int]] = {}

    def charging_stations(self):
        # TODO: implement
        raise NotImplementedError

    def get_available_locations(self, at_timeslot: int):
        try:
            return [
                location
                for location, capacity in self._availability[at_timeslot].items()
                if capacity > 0
            ]
        except KeyError as e:
            raise KeyError(f"Timeslot {at_timeslot} not in availability") from e

    def get_available_capacity(self, at_timeslot: int):
        try:
            return self._availability[at_timeslot]
        except KeyError as e:
            raise KeyError(f"Timeslot {at_timeslot} not in availability") from e

    def get_locations(self):
        """
        Defaults to `get_available_locations() at current time`
        TODO: shouldn't this incorporate a lookahead?
        """
        return self.get_available_locations(self._env.now)

    def update(self, timeslot: int, availability: Dict[str, int]):
        try:
            die_if_unbearable(availability, Dict[str, int])
            self._availability[timeslot] = availability
        except BeartypeDoorHintViolation as e:
            raise ValueError(
                "Availability must be a dict of (location, capacity)"
            ) from e

        # TODO: recreate all as virtual charging stations
        # self._virtual_charging_stations[timeslot] = []
        # for cs in self._charging_infrastructure.charging_stations:
        #     charging_station = VirtualChargingStation(
        #         cs, available_capacity=availability[cs.location]
        #     )
        #     self._virtual_charging_stations[timeslot].append(charging_station)
