from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from beartype.door import die_if_unbearable
from beartype.roar import BeartypeDoorHintViolation
from simpy import AnyOf

from simulation.helper.simulation_base import SimulationBase
from simulation.infrastructure.charging_stations.virtual_charging_station import (
    VirtualChargingStation,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from simulation.context.simulation_context import SimulationContext
    from simulation.infrastructure.charging_stations.charging_infastructure import (
        ChargingInfrastructure,
    )


class VirtualChargingInfrastructure(SimulationBase):
    """
    This class provides a virtual charging infrastructure (a special view on the physical charging infrastructure) to a certain observer.
    This could e.g. be fleet operators that are only allowed to charge at locations where they buy capacity.

    This class replicates the public API of ChargingInfrastructure.
    """

    __slots__ = (
        "_availability",
        "_charging_infrastructure",
        "_config",
        "_env",
        "_listeners",
        "_lookahead",
        "_use_virtual_cs",
        "_virtual_charging_stations",
    )

    def __init__(
        self,
        sim: SimulationContext,
        charging_infrastructure: ChargingInfrastructure,
        lookahead: int | None = None,
        use_virtual_cs: bool = True,
    ) -> None:
        super().__init__(sim)
        self._env = sim.env
        self._config = sim.config

        # if virtual charging infra is used to create a completely artificial plan of infrastructure, including future timeslots, use lookahead
        # otherwise, (if lookahead is None) be a mirror of the real underlying infrastructure, that can be updated from outside as needed

        self._lookahead = lookahead
        self._use_virtual_cs = use_virtual_cs

        if self._lookahead is None:
            self._availability: dict[str, int] = {
                station.location: station.capacity
                for station in charging_infrastructure.charging_stations
            }
        else:
            self._availability: dict[int, dict[str, int]] = {}

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
            self._listeners = {}
            for cs in self._virtual_charging_stations:
                self._env.process(self._sync_with_real(cs))
        else:
            self._listeners = None

    @property
    def charging_stations(self) -> list[VirtualChargingStation]:
        return self._charging_stations()

    def _charging_stations(self) -> list[VirtualChargingStation]:
        if self._virtual_charging_stations is None:
            raise NotImplementedError(
                "This virtual charging infrastructure was initialized without virtual charging stations!"
            )
        else:
            return self._virtual_charging_stations

    def get_available_locations(self, at_timeslot: int | None):  # noqa: ANN201
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

    def get_available_capacity(self, at_timeslot: int | None = None):  # noqa: ANN201
        if self._lookahead is None:
            return self._availability
        try:
            return self._availability[at_timeslot]
        except KeyError as e:
            raise KeyError(f"Timeslot {at_timeslot} not in availability") from e

    def get_locations(self) -> list[str]:
        """
        Defaults to `get_available_locations() at self._default_lookahead`
        which is the next timeslot that was already auctioned, or None
        """
        return self.get_available_locations(self._lookahead)

    def _update_virtual_cs(self, init: bool = False) -> None:
        for cs in self._virtual_charging_stations:
            # availability might be negative if we account for some vehicle on the way and in the meantime another vehicle arrives at the already full station
            bounded_capa = (
                max(
                    0,
                    min(
                        self._availability[self._lookahead][cs.location]
                        if self._lookahead is not None
                        else self._availability[cs.location],
                        cs._physical_charging_station.capacity,  # noqa: SLF001
                    ),
                )
                if not init
                else 0
            )
            cs.update_capacity(
                capacity=bounded_capa,
                valid_timeframe=(
                    self._lookahead,
                    self._lookahead
                    + self._config.shared_charging_auction.TIMESLOT_DURATION,
                )
                if self._lookahead is not None
                else None,
            )

    def update(self, availability: dict[str, int], timeslot: int | None = None) -> None:
        try:
            die_if_unbearable(availability, dict[str, int])
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
                self._config.shared_charging_auction.AUCTION_LOOKAHEAD
                - (
                    self._env.now
                    % self._config.shared_charging_auction.AUCTION_INTERVAL
                )
            )

        if self._virtual_charging_stations is not None:
            self._update_virtual_cs()

    def _sync_with_real(
        self, charging_station: VirtualChargingStation
    ) -> Generator[None, None, None]:
        cs = charging_station._physical_charging_station  # noqa: SLF001
        # Listener = namedtuple(
        #     "Listener", ["processed_plug_in_event", "processed_plug_out_event"]
        # )
        self._listeners[cs.id] = SimpleNamespace(
            processed_plug_in_event=self._env.event(),
            processed_plug_out_event=self._env.event(),
        )
        # self._listeners[cs.id] = {
        #     "processed_plug_in_event": self._env.event(),
        #     "processed_plug_out_event": self._env.event(),
        # }
        cs.register_event_subscriber(self._listeners[cs.id])

        while True:
            if (
                self._listeners[cs.id].processed_plug_in_event.triggered
                or self._listeners[cs.id].processed_plug_out_event.triggered
            ):
                # another listener has not processed the event, so the charging station hasn't reset ours yet
                yield self._env.timeout(1e-6)
                continue

            # listen for events from charging station
            event = yield AnyOf(
                self._env, [cs.vehicle_plugged_in, cs.vehicle_unplugged]
            )

            if cs.vehicle_plugged_in in event:
                self._availability[charging_station.location] -= 1
                if self._use_virtual_cs:
                    self._update_virtual_cs()
                self.logger.debug(
                    "Plugged in registered at %s.", charging_station.location
                )
                self._listeners[cs.id].processed_plug_in_event.succeed()
            elif cs.vehicle_unplugged in event:
                self._availability[charging_station.location] += 1
                if self._use_virtual_cs:
                    self._update_virtual_cs()
                self.logger.debug(
                    "Plugged out registered at %s.", charging_station.location
                )
                self._listeners[cs.id].processed_plug_out_event.succeed()
                self._listeners[cs.id].processed_plug_out_event.succeed()
