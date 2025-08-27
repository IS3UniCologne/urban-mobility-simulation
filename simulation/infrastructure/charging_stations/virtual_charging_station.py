from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    import simpy
    from shapely.geometry import Polygon

    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.infrastructure.charging_stations.charging_station import (
        ChargingStation,
    )
    from simulation.infrastructure.charging_stations.virtual_charging_infrastructure import (
        VirtualChargingInfrastructure,
    )


class VirtualChargingStation(SimulationBase):  # noqa: D101
    __slots = (
        "_env",
        "_valid_timeframe",
        "_capacity",
        "_polygon",
        "_centre",
        "_plugs",
        "_cs_id",
        "_location",
        "_power",
        "_queue",
        "_queue_size",
        "_current_queue_time",
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
        self._valid_timeframe = None
        self._capacity = charging_station.capacity
        self._polygon = charging_station.polygon
        self._centre = charging_station.centre
        self._plugs = charging_station.plugs  # reference, mutable object
        self._location = charging_station.location
        self._power = charging_station.power
        self._queue = charging_station._queue  # noqa: SLF001
        self._queue_size = charging_station._queue_size  # noqa: SLF001
        self._current_queue_time = charging_station._current_queue_time  # noqa: SLF001
        self._virtual_charging_infrastructure = virtual_charging_infrastructure

    def plug_in_notify(self) -> simpy.events.Generator:  # noqa: D102
        yield self._env.process(self._physical_charging_station.plug_in_notify())
        assert self._plugs.users == self._physical_charging_station.plugs.users

    def plug_out_notify(self) -> simpy.events.Generator:  # noqa: D102
        yield self._env.process(self._physical_charging_station.plug_out_notify())
        assert self._plugs.users == self._physical_charging_station.plugs.users

    def update_capacity(  # noqa: D102
        self, capacity: int, valid_timeframe: tuple[float, float] | None
    ) -> None:
        self._capacity = capacity
        self._valid_timeframe = valid_timeframe

    @property
    def virtual_charging_infrastructure(self) -> VirtualChargingInfrastructure:  # noqa: D102
        return self._virtual_charging_infrastructure

    @property
    def cs_id(self) -> int:
        """ID of the charging station in relation to the charging infrastructure it belongs to.

        Note: This ID is not globally unique across the entire simulation.
        For a globally unique identifier, use the `uid` property inherited from SimulationBase."""  # noqa: D209
        return self._cs_id

    def valid_timeframe(self) -> tuple[float, float] | None:  # noqa: D102
        return self._valid_timeframe

    @property
    def capacity(self) -> int:  # noqa: D102
        return self._capacity

    @property
    def plugs(self) -> simpy.PriorityResource:  # noqa: D102
        return self._plugs

    @property
    def power(self) -> float:  # noqa: D102
        return self._power

    @property
    def centre(self) -> GeodesicPosition:  # noqa: D102
        return self._centre

    @property
    def location(self) -> str:  # noqa: D102
        return self._location

    @property
    def polygon(self) -> Polygon:  # noqa: D102
        return self._polygon

    @property
    def queue_size(self) -> int:  # noqa: D102
        return self._queue_size

    @property
    def current_queue_time(self) -> float:  # noqa: D102
        return self._physical_charging_station.current_queue_time
