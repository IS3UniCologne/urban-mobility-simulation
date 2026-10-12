"""Per-operator virtual view of a physical charging station."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from collections.abc import Generator

    import simpy
    from shapely.geometry import Polygon
    from simpy import Event

    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.types import RegionId
    from simulation.infrastructure.charging_stations.charging_station import (
        ChargingStation,
    )
    from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
        VirtualChargingInfrastructure,
    )


class VirtualChargingStation(SimulationBase):
    """Virtual view of a physical charging station for a single operator.

    Mirrors the physical station's plugs and queue while tracking
    operator-specific capacity reservations.

    Parameters
    ----------
    charging_station : ChargingStation
        Backing physical charging station.
    virtual_charging_infrastructure : VirtualChargingInfrastructure
        Owning virtual infrastructure.
    """

    __slots__ = (
        "_blocked_capacity",
        "_capacity",
        "_centre",
        "_cs_id",
        "_current_queue_time",
        "_env",
        "_location",
        "_physical_charging_station",
        "_plugs",
        "_polygon",
        "_power",
        "_queue",
        "_queue_size",
        "_valid_timeframe",
        "_virtual_charging_infrastructure",
    )

    def __init__(
        self,
        charging_station: ChargingStation,
        virtual_charging_infrastructure: VirtualChargingInfrastructure,
    ) -> None:
        super().__init__(charging_station._sim)  # noqa: SLF001
        self._cs_id = charging_station.cs_id
        self._env = charging_station._env  # noqa: SLF001
        self._physical_charging_station = charging_station
        self._valid_timeframe: tuple[float, float] | None = None
        self._capacity = charging_station.capacity
        self._blocked_capacity = 0
        self._polygon = charging_station.polygon
        self._centre = charging_station.centre
        self._plugs = charging_station.plugs  # reference, mutable object
        self._location = charging_station.location
        self._power = charging_station.power
        self._queue = charging_station._queue  # noqa: SLF001
        self._queue_size = charging_station._queue_size  # noqa: SLF001
        self._current_queue_time = charging_station._current_queue_time  # noqa: SLF001
        self._virtual_charging_infrastructure = virtual_charging_infrastructure

    def plug_in_notify(self) -> Generator[Event, None, None]:
        """Forward a plug-in notification to the physical station.

        Yields
        ------
        simpy.Event
            Process event for the physical station's plug-in.
        """
        yield self._env.process(self._physical_charging_station.plug_in_notify())
        assert self._plugs.users == self._physical_charging_station.plugs.users

    def plug_out_notify(self) -> Generator[Event, None, None]:
        """Forward a plug-out notification to the physical station.

        Yields
        ------
        simpy.Event
            Process event for the physical station's plug-out.
        """
        yield self._env.process(self._physical_charging_station.plug_out_notify())
        assert self._plugs.users == self._physical_charging_station.plugs.users

    def update_capacity(
        self, capacity: int, valid_timeframe: tuple[float, float] | None
    ) -> None:
        """Set the operator-visible capacity and its valid timeframe.

        Capacity is clamped to [0, physical capacity]; a negative input records
        blocked capacity instead.
        """
        self._capacity = max(0, min(capacity, self._physical_charging_station.capacity))
        if capacity < 0:
            self._blocked_capacity = -capacity
        else:
            self._blocked_capacity = 0
        self._valid_timeframe = valid_timeframe

    @property
    def virtual_charging_infrastructure(self) -> VirtualChargingInfrastructure:
        """Owning virtual charging infrastructure."""
        return self._virtual_charging_infrastructure

    @property
    def timeslot_duration(self) -> int | None:
        """Duration of one coordination timeslot in minutes."""
        return self._virtual_charging_infrastructure._charging_infrastructure._charging_infra_config.COORDINATION_TIMESLOT_DURATION  # noqa: SLF001

    def timeslot_end(self, scheduled_time: float | None) -> float | None:
        """Return scheduled_time + timeslot_duration if a valid timeframe exists, else None.

        Parameters
        ----------
        scheduled_time : float or None
            The scheduled start time of the timeslot.

        Returns
        -------
        float or None
            End of the timeslot, or None if no active timeslot or scheduled_time is None.
        """
        if self._valid_timeframe is None or scheduled_time is None:
            return None
        assert self.timeslot_duration is not None
        return scheduled_time + self.timeslot_duration

    @property
    def cs_id(self) -> int:
        """ID of the charging station in relation to the charging infrastructure it belongs to.

        Note: This ID is not globally unique across the entire simulation.
        For a globally unique identifier, use the `uid` property inherited from SimulationBase.
        """
        return self._cs_id

    @property
    def valid_timeframe(self) -> tuple[float, float] | None:
        """Timeframe over which the current capacity applies, or None."""
        return self._valid_timeframe

    @property
    def capacity(self) -> int:
        """Operator-visible capacity."""
        return self._capacity

    @property
    def blocked_capacity(self) -> int:
        """Capacity blocked from this operator."""
        return self._blocked_capacity

    @property
    def plugs(self) -> simpy.PriorityResource:
        """Shared plug resource of the physical station."""
        return self._plugs

    @property
    def power(self) -> float:
        """Charging power in kW."""
        return self._power

    @property
    def price_per_kWh(self) -> float:
        """Current price per kWh of the charging station."""
        return self._physical_charging_station.price_per_kWh

    @property
    def centre(self) -> GeodesicPosition:
        """Centroid position of the station's cell."""
        return self._centre

    @property
    def location(self) -> RegionId:
        """Region id of the station."""
        return self._location

    @property
    def polygon(self) -> Polygon:
        """Cell boundary polygon."""
        return self._polygon

    @property
    def queue_size(self) -> int:
        """Maximum queue length."""
        return self._queue_size

    @property
    def current_queue_time(self) -> float:
        """Current estimated queue wait time of the physical station."""
        return self._physical_charging_station.current_queue_time
