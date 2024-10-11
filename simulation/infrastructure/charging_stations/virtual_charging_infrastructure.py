from typing import Dict

from beartype.door import die_if_unbearable
from beartype.roar import BeartypeDoorHintViolation

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
        "_default_lookahead",
        "_availability",
        "_charging_infrastructure",
        "_virtual_charging_stations",
    )

    def __init__(
        self,
        env,
        charging_infrastructure: ChargingInfrastructure,
        default_lookahead: int,
        use_virtual_cs=True,
    ):
        self._env = env
        self._config = Configuration.instance()

        # self._default_lookahead = (
        #     self._config.auction_config.auction_start
        #     + self._config.shared_charging_config.auction_lookahead
        # )
        self._default_lookahead = default_lookahead

        self._availability: Dict[int, Dict[str, int]] = {}

        self._charging_infrastructure = charging_infrastructure
        if use_virtual_cs:
            self._virtual_charging_stations = [
                VirtualChargingStation(cs)
                for cs in self._charging_infrastructure.charging_stations
            ]

            self._update_virtual_cs(init=True)
        else:
            self._virtual_charging_stations = None

    # TODO: listen for start and end charge events from charging stations to update virtual charging stations, using ids of vehicles to check

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
        Defaults to `get_available_locations() at self._default_lookahead`
        which is the next timeslot that was already auctioned.
        """
        return self.get_available_locations(self._default_lookahead)

    def _update_virtual_cs(self, init=False):
        for cs in self._virtual_charging_stations:
            cs.update_capacity(
                capacity=self._availability[self._default_lookahead][cs.location]
                if not init
                else 0,
                valid_timeframe=(
                    self._default_lookahead,
                    self._default_lookahead
                    + self._config.shared_charging_config.timeslot_duration,
                ),
            )

    def update(self, timeslot: int, availability: Dict[str, int]):
        try:
            die_if_unbearable(availability, Dict[str, int])
            self._availability[timeslot] = availability
        except BeartypeDoorHintViolation as e:
            raise ValueError(
                "Availability must be a dict of (location, capacity)"
            ) from e

        # update the default lookahead to be the next auctioned slot
        self._default_lookahead = self._env.now + (
            self._config.shared_charging_config.auction_lookahead
            - (self._env.now % self._config.shared_charging_config.auction_interval)
        )

        if self._virtual_charging_stations is not None:
            self._update_virtual_cs()
