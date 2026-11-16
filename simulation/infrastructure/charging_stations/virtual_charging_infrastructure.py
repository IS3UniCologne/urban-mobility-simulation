"""Per-observer virtual view of the physical charging infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from beartype.door import die_if_unbearable
from beartype.roar import BeartypeDoorHintViolation
from simpy import AnyOf

from simulation.helper.simulation_base import SimulationBase
from simulation.infrastructure.charging_stations.virtual_charging_station import (
    VirtualChargingStation,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.types import RegionId, SimId
    from simulation.infrastructure.charging_stations.charging_infrastructure import (
        ChargingInfrastructure,
    )


class _PlugEventListener:
    """Holder of plug-in/out acknowledgement events for one station."""

    __slots__ = ("processed_plug_in_event", "processed_plug_out_event")

    def __init__(
        self, processed_plug_in_event: Event, processed_plug_out_event: Event
    ) -> None:
        self.processed_plug_in_event = processed_plug_in_event
        self.processed_plug_out_event = processed_plug_out_event


class VirtualChargingInfrastructure(SimulationBase):
    """Observer-specific view on the physical charging infrastructure.

    Used e.g. by fleet operators only allowed to charge where they bought
    capacity. Replicates the public API of ChargingInfrastructure.
    TODO: enforce that shared API.

    ALSO TODO: The heterogeneity introduced by the lookahead and virtual_cs options is a bit awkward;
    we might want to split this in the future

    Parameters
    ----------
    sim : SimulationContext
        Simulation context.
    charging_infrastructure : ChargingInfrastructure
        Backing physical infrastructure.
    lookahead : int or None
        If set, build an artificial plan over future timeslots; if None, mirror
        the underlying infrastructure and update from outside as needed.
    use_virtual_cs : bool
        Whether to create VirtualChargingStation views over the physical stations.
    """

    __slots__ = (
        "_availability",
        "_charging_infrastructure",
        "_charging_stations_by_location",
        "_current_lookahead",
        "_env",
        "_listeners",
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

        # if virtual charging infra is used to create a completely artificial plan of infrastructure, including future timeslots, use lookahead
        # otherwise, (if lookahead is None) be a mirror of the real underlying infrastructure, that can be updated from outside as needed

        self._current_lookahead: float | None = lookahead
        self._use_virtual_cs = use_virtual_cs

        # Without lookahead, availability maps location -> free capacity. With
        # lookahead, it maps timeslot -> (location -> free capacity).
        self._availability: dict[RegionId, int] | dict[float, dict[RegionId, int]]
        if self._current_lookahead is None:
            self._availability = {
                station.location: station.capacity
                for station in charging_infrastructure.charging_stations
            }
        else:
            self._availability = {}

        self._charging_infrastructure = charging_infrastructure
        self._virtual_charging_stations: list[VirtualChargingStation] | None
        if use_virtual_cs:
            self._virtual_charging_stations = [
                VirtualChargingStation(
                    charging_station=cs, virtual_charging_infrastructure=self
                )
                for cs in self._charging_infrastructure.charging_stations
            ]
            self._charging_stations_by_location = {
                cs.location: cs for cs in self._virtual_charging_stations
            }
            if self._current_lookahead is not None:
                self._update_virtual_cs(init=True)
        else:
            self._virtual_charging_stations = None

        self._listeners: dict[SimId, _PlugEventListener] | None
        if self._current_lookahead is None and self._use_virtual_cs:
            self._listeners = {}
            for cs in self._charging_stations():
                self._env.process(self._sync_with_real(cs))
        else:
            self._listeners = None

    @property
    def charging_stations(self) -> list[VirtualChargingStation]:  # noqa: D102
        return self._charging_stations()

    def _charging_stations(self) -> list[VirtualChargingStation]:
        if self._virtual_charging_stations is None:
            raise NotImplementedError(
                "This virtual charging infrastructure was initialized without virtual charging stations!"
            )
        else:
            return self._virtual_charging_stations

    def get_available_locations(self, at_timeslot: float | None) -> list[RegionId]:
        """Locations with positive available capacity, optionally at a timeslot."""
        if at_timeslot is None:
            location_avail = cast("dict[RegionId, int]", self._availability)
            return [loc for loc, capacity in location_avail.items() if capacity > 0]

        timeslot_avail = cast("dict[float, dict[RegionId, int]]", self._availability)
        try:
            return [
                loc
                for loc, capacity in timeslot_avail[at_timeslot].items()
                if capacity > 0
            ]
        except KeyError as e:
            raise KeyError(f"Timeslot {at_timeslot} not in availability") from e

    def get_available_capacity(
        self, at_timeslot: float | None = None
    ) -> dict[float, dict[RegionId, int]] | dict[RegionId, int]:
        """Available capacity, by location (no lookahead) or for a timeslot."""
        if self._current_lookahead is None:
            return cast("dict[RegionId, int]", self._availability)
        timeslot_avail = cast("dict[float, dict[RegionId, int]]", self._availability)
        if at_timeslot is None:
            raise KeyError("A timeslot must be given when a lookahead is set")
        try:
            return timeslot_avail[at_timeslot]
        except KeyError as e:
            raise KeyError(f"Timeslot {at_timeslot} not in availability") from e

    def get_locations(self) -> list[RegionId]:
        """Available locations at the current lookahead (next auctioned slot, or None)."""
        return self.get_available_locations(self._current_lookahead)

    def _update_virtual_cs(self, init: bool = False) -> None:
        lookahead = self._current_lookahead
        if lookahead is not None:
            duration = self._charging_infrastructure._charging_infra_config.COORDINATION_TIMESLOT_DURATION  # noqa: SLF001
            assert duration is not None
            valid_timeframe: tuple[float, float] | None = (
                lookahead,
                lookahead + duration,
            )
        else:
            valid_timeframe = None

        for cs in self._charging_stations():
            # availability might be negative if we account for some vehicle on the way and in the meantime another vehicle arrives at the already full station
            if init:
                capa = 0
            elif lookahead is not None:
                timeslot_avail = cast(
                    "dict[float, dict[RegionId, int]]", self._availability
                )
                capa = timeslot_avail[lookahead][cs.location]
            else:
                location_avail = cast("dict[RegionId, int]", self._availability)
                capa = location_avail[cs.location]

            cs.update_capacity(capacity=capa, valid_timeframe=valid_timeframe)

    def update(
        self, availability: dict[RegionId, int], timeslot: int | None = None
    ) -> None:
        """Update availability, lookahead and virtual stations.

        Parameters
        ----------
        availability : dict of RegionId to int
            New free capacity per location.
        timeslot : int or None
            Target timeslot; required when a lookahead is set, ignored otherwise.

        Raises
        ------
        ValueError
            If availability is not a dict of (location, capacity).
        """
        try:
            die_if_unbearable(availability, dict[str, int])
            if self._current_lookahead is None:
                self._availability = availability
            else:
                timeslot_avail = cast(
                    "dict[float, dict[RegionId, int]]", self._availability
                )
                assert timeslot is not None
                timeslot_avail[timeslot] = availability
                # This is super awkward, but hard to avoid, see todo at the top
        except BeartypeDoorHintViolation as e:
            raise ValueError(
                "Availability must be a dict of (location, capacity)"
            ) from e
        if self._current_lookahead is not None:
            config = self._charging_infrastructure._charging_infra_config  # noqa: SLF001
            assert config.COORDINATION_LOOKAHEAD is not None
            assert config.COORDINATION_INTERVAL is not None
            # update the current lookahead to be the next coordinated (e.g. auctioned) slot
            self._current_lookahead = self._env.now + (
                config.COORDINATION_LOOKAHEAD
                - (self._env.now % config.COORDINATION_INTERVAL)
            )

        if self._virtual_charging_stations is not None:
            self._update_virtual_cs()

    def _sync_with_real(
        self, charging_station: VirtualChargingStation
    ) -> Generator[Event, Any, None]:
        assert self._listeners is not None
        location_avail = cast("dict[RegionId, int]", self._availability)
        cs = charging_station._physical_charging_station  # noqa: SLF001
        # Listener = namedtuple(
        #     "Listener", ["processed_plug_in_event", "processed_plug_out_event"]
        # )
        self._listeners[cs.uid] = _PlugEventListener(
            processed_plug_in_event=self._env.event(),
            processed_plug_out_event=self._env.event(),
        )
        cs.register_event_subscriber(self._listeners[cs.uid])

        while True:
            if (
                self._listeners[cs.uid].processed_plug_in_event.triggered
                or self._listeners[cs.uid].processed_plug_out_event.triggered
            ):
                # another listener has not processed the event, so the charging station hasn't reset ours yet
                yield self._env.timeout(1e-6)
                continue

            # listen for events from charging station
            event = yield AnyOf(
                self._env, [cs.vehicle_plugged_in, cs.vehicle_unplugged]
            )

            if cs.vehicle_plugged_in in event:
                location_avail[charging_station.location] -= 1
                if self._use_virtual_cs:
                    self._update_virtual_cs()
                self.logger.debug(
                    "Plugged in registered at %s.", charging_station.location
                )
                self._listeners[cs.uid].processed_plug_in_event.succeed()
            elif cs.vehicle_unplugged in event:
                location_avail[charging_station.location] += 1
                if self._use_virtual_cs:
                    self._update_virtual_cs()
                self.logger.debug(
                    "Plugged out registered at %s.", charging_station.location
                )
                self._listeners[cs.uid].processed_plug_out_event.succeed()

    def get_charging_station_by_location(
        self, location: RegionId
    ) -> VirtualChargingStation:
        """Virtual charging station at the given location."""
        return self._charging_stations_by_location[location]
