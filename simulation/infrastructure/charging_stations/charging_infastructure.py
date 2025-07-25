from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext

from simulation.infrastructure.charging_stations.charging_station import ChargingStation


class ChargingInfrastructure:
    __instance = None

    __slots__ = (
        "_capacity_list",
        "_charging_stations",
        "_location_list",
        "_power_list",
        "_queue_size",
        "_sim",
        "_tracking",
    )

    @staticmethod
    def instance() -> ChargingInfrastructure:
        """Static access method."""
        if ChargingInfrastructure.__instance is None:
            raise Exception("ChargingInfrastructure was not initialized")
        else:
            return ChargingInfrastructure.__instance

    @staticmethod
    def init(
        sim: SimulationContext,
        location_list: list[str],
        power_list: list[float],
        capacity_list: list[int],
        queue_size: list[int],
        reset: bool = False,
    ) -> None | ChargingInfrastructure:
        """Static access method."""
        if ChargingInfrastructure.__instance is None or reset is True:
            ChargingInfrastructure(
                sim, location_list, power_list, capacity_list, queue_size, reset
            )
        return ChargingInfrastructure.__instance

    def __init__(
        self,
        sim: SimulationContext,
        location_list: list[str],
        power_list: list[float],
        capacity_list: list[int],
        queue_size: list[int],
        reset: bool = False,
    ) -> None:
        """Virtually private constructor."""
        if ChargingInfrastructure.__instance is not None and not reset:
            raise Exception("This class is a singleton!")
        else:
            ChargingInfrastructure.__instance = self
            super(ChargingInfrastructure, self).__init__()  # noqa: UP008
        self._sim = sim
        self._location_list = location_list
        self._power_list = power_list
        self._capacity_list = capacity_list
        self._queue_size = queue_size
        self._charging_stations = []  # a list of charger objects
        self._initialise_charging_stations()

    def _initialise_charging_stations(self) -> None:
        for i, location in enumerate(self._location_list):
            charging_station = ChargingStation(
                sim=self._sim,
                location=location,
                power=self._power_list[i],
                capacity=self._capacity_list[i],
                queue_size=self._queue_size[i],
            )
            self._charging_stations.append(charging_station)

    @property
    def charging_stations(self) -> list[ChargingStation]:
        return self._charging_stations

    def get_locations(self) -> list[str]:
        return self._location_list
        return self._location_list
