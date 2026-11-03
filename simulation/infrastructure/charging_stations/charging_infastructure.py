"""Physical charging infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from simulation.infrastructure.charging_stations.charging_station import ChargingStation
from simulation.helper.time import MINUTES_PER_HOUR, SimulationTimeConverter

if TYPE_CHECKING:
    from collections.abc import Generator
    from simpy import Event

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
        "_charging_price_profile",
        "_charging_stations",
        "_charging_stations_by_location",
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
        self._charging_price_profile = (
            charging_infrastructure_config.CHARGING_STATION_PRICE_PROFILE
        )
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
        self._sim.env.process(
            self._broadcast_prices()
        )  # updates charging prices at each hour

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
                charging_infrastructure=self,
            )
            self._charging_stations.append(charging_station)
            self._charging_stations_by_location[location] = charging_station

    def _broadcast_prices(self) -> Generator[Event, None, None]:
        """Send the current hour's price per kWh to all stations at every full hour."""
        env = self._sim.env
        while True:
            price = self._charging_price_profile[SimulationTimeConverter.hours(env.now)]
            for station in self._charging_stations:
                station.update_price(price)
            # wait until the next full hour, also if the simulation starts mid-hour
            yield env.timeout(MINUTES_PER_HOUR - env.now % MINUTES_PER_HOUR)

    def average_price(self, start: float, end: float) -> float:
        """Time-weighted price per kWh for chargign between start and end.

        A session that from 17.40 to 18.50 pays 20 minutes at the 17.00 price and 50
        minutes at the 18.00 price. Charging power is constant, so energy is spread
        evenly over the session.

        Parameters
        ----------
        start : float
            Start time of charging session in simulation minutes.
        end : float
            End of charging session in simulation minutes.

        Returns
        -------
        float
            Average price per kWh for the session.
        """
        if end <= start:
            return self._charging_price_profile[SimulationTimeConverter.hours(start)]

        cost = 0.0
        t = start
        while t < end:
            hour_end = min(end, (t // MINUTES_PER_HOUR + 1) * MINUTES_PER_HOUR)
            cost += (hour_end - t) * self._charging_price_profile[
                SimulationTimeConverter.hours(t)
            ]
            t = hour_end

        return cost / (end - start)

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
