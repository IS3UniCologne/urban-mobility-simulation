from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import (
        ChargingInfrastructureConfig,
    )
    from simulation.world.markets.auction import Auction

from simulation.infrastructure.charging_stations.charging_station import ChargingStation


class ChargingInfrastructure:
    __instance = None

    __slots__ = (
        "_auction",
        "_capacity_list",
        "_charging_infra_config",
        "_charging_stations",
        "_location_list",
        "_power_list",
        "_queue_size",
        "_sim",
        "_tracking",
    )

    def __init__(
        self,
        sim: SimulationContext,
        charging_infrastructure_config: ChargingInfrastructureConfig,
    ) -> None:
        self._sim = sim
        self._location_list = charging_infrastructure_config.LOCATIONS
        self._power_list = charging_infrastructure_config.CHARGING_STATION_POWER
        self._capacity_list = charging_infrastructure_config.CHARGING_STATION_CAPACITY
        self._queue_size = charging_infrastructure_config.CHARGING_STATION_QUEUE_SIZE

        if charging_infrastructure_config.AUCTION_CONFIG:
            charging_infrastructure_config.COORDINATION_LOOKAHEAD = (
                charging_infrastructure_config.AUCTION_CONFIG.AUCTION_LOOKAHEAD
            )
            charging_infrastructure_config.COORDINATION_INTERVAL = (
                charging_infrastructure_config.AUCTION_CONFIG.AUCTION_INTERVAL
            )
            charging_infrastructure_config.COORDINATION_TIMESLOT_DURATION = (
                charging_infrastructure_config.AUCTION_CONFIG.TIMESLOT_DURATION
            )

        self._charging_infra_config = charging_infrastructure_config

        self._charging_stations = []  # a list of charger objects
        self._initialise_charging_stations()

        self._auction = self._initialize_auction()

    def _initialize_auction(self) -> Auction | None:
        # TODO: @janikmu decouple VCI and auction - go for "coordination" or something

        if self._charging_infra_config.AUCTION_CONFIG:
            auction = self._charging_infra_config.AUCTION_CONFIG.AUCTION_TYPE(
                sim=self._sim,
                charging_infrastructure=self,
                shared_charging_config=self._charging_infra_config.AUCTION_CONFIG,
            )

            return auction

        else:
            return None

    def _initialise_charging_stations(self) -> None:
        for i, location in enumerate(self._location_list):
            charging_station = ChargingStation(
                sim=self._sim,
                cs_id=i,
                location=location,
                power=self._power_list[i],
                capacity=self._capacity_list[i],
                queue_size=self._queue_size[i],
            )
            self._charging_stations.append(charging_station)

    @property
    def charging_stations(self) -> list[ChargingStation]:
        return self._charging_stations

    @property
    def auction(self) -> Auction | None:
        return self._auction

    def get_locations(self) -> list[str]:
        return self._location_list
