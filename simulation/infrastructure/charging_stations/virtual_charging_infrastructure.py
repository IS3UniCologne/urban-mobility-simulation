from typing import Dict, Optional

from beartype.door import die_if_unbearable
from beartype.roar import BeartypeDoorHintViolation
from simpy import AnyOf

from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.infrastructure.charging_stations.virtual_charging_station import (
    VirtualChargingStation,
)


class VirtualChargingInfrastructure:
    """
    This class provides a virtual charging infrastructure (a special view on the physical charging infrastructure) to a certain observer.
    This could e.g. be fleet operators that are only allowed to charge at locations where they buy capacity.

    This class replicates the public API of ChargingInfrastructure.
    """

    __slots__ = (
        "_env",
        "_config",
        "_lookahead",
        "_use_virtual_cs",
        "_availability",
        "_charging_infrastructure",
        "_virtual_charging_stations",
    )

    def __init__(
        self,
        env,
        charging_infrastructure: ChargingInfrastructure,
        lookahead: Optional[int] = None,
        use_virtual_cs=True,
    ):
        self._env = env
        self._config = Configuration.instance()

        # if virtual charging infra is used to create a completely artificial plan of infrastructure, including future timeslots, use lookahead
        # otherwise, (if lookahead is None) be a mirror of the real underlying infrastructure, that can be updated from outside as needed

        self._lookahead = lookahead
        self._use_virtual_cs = use_virtual_cs

        if self._lookahead is None:
            self._availability: Dict[str, int] = {
                station.location: station.capacity
                for station in charging_infrastructure.charging_stations
            }
        else:
            self._availability: Dict[int, Dict[str, int]] = {}

        self._charging_infrastructure = charging_infrastructure
        if use_virtual_cs:
            self._virtual_charging_stations = [
                VirtualChargingStation(cs)
                for cs in self._charging_infrastructure.charging_stations
            ]
            if self._lookahead is not None:
                self._update_virtual_cs(init=True)
        else:
            self._virtual_charging_stations = None

        if self._lookahead is None and self._use_virtual_cs:
            for cs in self._virtual_charging_stations:
                self._env.process(self._sync_with_real(cs))

    @property
    def charging_stations(self):
        return self._charging_stations()

    def _charging_stations(self):
        if self._virtual_charging_stations is None:
            raise NotImplementedError(
                "This virtual charging infrastructure was initialized without virtual charging stations!"
            )
        else:
            return self._virtual_charging_stations

    def get_available_locations(self, at_timeslot: Optional[int]):
        if at_timeslot is None:
            return [
                location
                for location, capacity in self._availability.items()
                if capacity > 0
            ]

        try:
            return [
                location
                for location, capacity in self._availability[at_timeslot].items()
                if capacity > 0
            ]
        except KeyError as e:
            raise KeyError(f"Timeslot {at_timeslot} not in availability") from e

    def get_available_capacity(self, at_timeslot: Optional[int] = None):
        if self._lookahead is None:
            return self._availability
        try:
            return self._availability[at_timeslot]
        except KeyError as e:
            raise KeyError(f"Timeslot {at_timeslot} not in availability") from e

    def get_locations(self):
        """
        Defaults to `get_available_locations() at self._default_lookahead`
        which is the next timeslot that was already auctioned, or None
        """
        return self.get_available_locations(self._lookahead)

    def _update_virtual_cs(self, init=False):
        for cs in self._virtual_charging_stations:
            cs.update_capacity(
                capacity=(
                    self._availability[self._lookahead][cs.location]
                    if self._lookahead is not None
                    else self._availability[cs.location]
                )
                if not init
                else 0,
                valid_timeframe=(
                    self._lookahead,
                    self._lookahead
                    + self._config.shared_charging_config.timeslot_duration,
                )
                if self._lookahead is not None
                else None,
            )

    def update(self, availability: Dict[str, int], timeslot: Optional[int] = None):
        try:
            die_if_unbearable(availability, Dict[str, int])
            if self._lookahead is None:
                self._availability = availability
            else:
                self._availability[timeslot] = availability
        except BeartypeDoorHintViolation as e:
            raise ValueError(
                "Availability must be a dict of (location, capacity)"
            ) from e
        if self._lookahead is not None:
            # update the default lookahead to be the next auctioned slot
            self._lookahead = self._env.now + (
                self._config.shared_charging_config.auction_lookahead
                - (self._env.now % self._config.shared_charging_config.auction_interval)
            )

        if self._virtual_charging_stations is not None:
            self._update_virtual_cs()

    def _sync_with_real(self, charging_station: VirtualChargingStation):
        cs = charging_station._physical_charging_station
        while True:
            event = yield AnyOf(
                self._env, [cs.vehicle_plugged_in, cs.vehicle_unplugged]
            )

            if cs.vehicle_plugged_in in event:
                self._availability[charging_station.location] -= (
                    1 if not self._availability[charging_station.location] == 0 else 0
                )
                if self._virtual_charging_stations is not None:
                    self._update_virtual_cs()
                cs._vehicle_plugged_in = self._env.event()
            elif cs.vehicle_unplugged in event:
                self._availability[charging_station.location] += (
                    1
                    if not self._availability[charging_station.location] == cs.capacity
                    else 0
                )
                if self._virtual_charging_stations is not None:
                    self._update_virtual_cs()
                cs._vehicle_unplugged = self._env.event()
