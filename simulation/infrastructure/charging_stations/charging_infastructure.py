"""Physical charging infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from simulation.infrastructure.charging_stations.charging_station import ChargingStation

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import (
        ChargingInfrastructureConfig,
        SharedChargingAuctionConfig,
    )
    from simulation.helper.types import RegionId
    from simulation.world.markets.auction import Auction
    from simulation.world.markets.shared_charging_auction import SharedChargingAuction


class ChargingInfrastructure:
    """Collection of physical charging stations and their coordination auction.

    Parameters
    ----------
    sim : SimulationContext
        Active simulation context.
    charging_infrastructure_config : ChargingInfrastructureConfig
        Charging-station locations, powers, capacities and auction settings.
    """

    __instance = None

    __slots__ = (
        "_auction",
        "_capacity_list",
        "_charging_infra_config",
        "_charging_stations",
        "_charging_stations_by_location",
        "_cost_per_kWh_list",
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
        self._cost_per_kWh_list = charging_infrastructure_config.CHARGING_STATION_COST_PER_KWH
        if charging_infrastructure_config.AUCTION_CONFIG:
            # TODO: Remove this hack once the auction modules are fully typed.
            auction_config = cast(
                "SharedChargingAuctionConfig",
                charging_infrastructure_config.AUCTION_CONFIG,
            )
            charging_infrastructure_config.COORDINATION_LOOKAHEAD = (
                auction_config.AUCTION_LOOKAHEAD
            )
            charging_infrastructure_config.COORDINATION_INTERVAL = (
                auction_config.AUCTION_INTERVAL
            )
            charging_infrastructure_config.COORDINATION_TIMESLOT_DURATION = (
                auction_config.TIMESLOT_DURATION
            )

        self._charging_infra_config = charging_infrastructure_config

        self._charging_stations: list[ChargingStation] = []
        # fast lookup of charging stations by location
        self._charging_stations_by_location: dict[RegionId, ChargingStation] = {}
        self._initialise_charging_stations()

        self._auction = self._initialize_auction()

    def _initialize_auction(self) -> Auction | None:
        # TODO: @janikmu decouple VCI and auction - go for "coordination" or something

        if self._charging_infra_config.AUCTION_CONFIG:
            auction_config = cast(
                "SharedChargingAuctionConfig",
                self._charging_infra_config.AUCTION_CONFIG,
            )
            auction_type = cast(
                "type[SharedChargingAuction]", auction_config.AUCTION_TYPE
            )
            return auction_type(
                sim=self._sim,
                charging_infrastructure=self,
                shared_charging_config=auction_config,
            )

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
                cost_per_kWh=self._cost_per_kWh_list[i],
            )
            self._charging_stations.append(charging_station)
            self._charging_stations_by_location[location] = charging_station

    @property
    def charging_stations(self) -> list[ChargingStation]:
        """Physical charging stations."""
        return self._charging_stations

    @property
    def auction(self) -> Auction | None:
        """Coordination auction, or None if not configured."""
        return self._auction

    def get_locations(self) -> list[RegionId]:
        """Region ids with charging stations."""
        return self._location_list

    def get_charging_station_by_location(self, location: RegionId) -> ChargingStation:
        """Return the charging station at the given location."""
        return self._charging_stations_by_location[location]
