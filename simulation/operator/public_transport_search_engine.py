from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import TransitOperatorConfig
    from simulation.infrastructure.transit_network.stop import Stop
    from simulation.operator.data_transfer_object.transport_request import (
        TransportRequest,
    )
    from simulation.operator.public_transport_vehicle_fleet import (
        PublicTransportVehicleFleet,
    )
    from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle

from simulation.helper.simulation_base import SimulationBase
from simulation.helper.time import SimulationTimeConverter
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface


class PublicTransportSearchEngine(SearchEngineInterface, SimulationBase):
    """
    Search engine for public transport buses.

    Parameters
    ----------
    sim : SimulationContext
        Simulation context.
    fleet : PublicTransportVehicleFleet
        Fleet whose buses are searched.
    operator_config : TransitOperatorConfig
        Configuration of the transit operator.
    """

    __slots__ = ("_env", "_fleet", "_operator_config", "_sim", "_user_config")

    def __init__(
        self,
        sim: SimulationContext,
        fleet: PublicTransportVehicleFleet,
        operator_config: TransitOperatorConfig,
    ) -> None:
        super().__init__(sim=sim)
        self._sim = sim
        self._env = sim.env
        self._fleet = fleet
        self._operator_config = operator_config
        self._user_config = self._sim.config.user

    def find_viable_transit(  # noqa: ANN201, D102
        self,
        transportation_search_task,  # noqa: ANN001
        spatial_strategy="hexagon",  # noqa: ANN001
        temporal_lookahead=10,  # noqa: ANN001
    ):
        search_time = transportation_search_task.transport_task.time
        latest_departure = SimulationTimeConverter.as_str(
            search_time + temporal_lookahead
        )
        walk_alternative = (
            transportation_search_task.transport_task.origin
            >> transportation_search_task.transport_task.destination
        )

        viable_transit = []
        busses = self._fleet.get_busses()

        if not busses:
            # No busses are en-route, report no viable alternative
            # TODO: fallback to timetable if temporal_lookahead > transit operator planning window?
            if (
                temporal_lookahead
                > self._operator_config.OPERATIONS_CONFIG.PLANNING_LOOKAHEAD
            ):
                raise NotImplementedError(
                    "temporal lookahead of user > planning lookahead of operator currently not supported"
                )

        for vehicle in busses:
            viable_stops = self._check_viable_stops(
                vehicle,
                spatial_strategy,
                transportation_search_task.transport_task.origin,
                transportation_search_task.transport_task.destination,
            )
            if viable_stops:
                # check for temporal alignment
                reachable_stops = []
                for stop in viable_stops["origin"]:
                    reachable, distance = self._reachable_in_time(
                        stop,
                        vehicle,
                        search_time,
                        transportation_search_task.transport_task.origin,
                        latest_departure,
                    )
                    if reachable:
                        reachable_stops.append(
                            (stop, distance)
                        )  # tuple of (Stop, walking distance to/from)

                if reachable_stops:
                    self.logger.debug(
                        "Bus %s is a viable transport alternative from %s to %s!",
                        vehicle.uid,
                        transportation_search_task.transport_task.origin,
                        transportation_search_task.transport_task.destination,
                    )

                    # build all possible combinations of viable subroutes
                    for start, walk_to_start in reachable_stops:
                        for end in viable_stops["destination"]:
                            if start.stop_id >= end.stop_id:
                                # only look at travel in the right direction
                                continue

                            subroute = vehicle.route.subroute(start, end)
                            walk_from_end = (
                                end
                                >> transportation_search_task.transport_task.destination
                            )

                            if (
                                walk_to_start >= walk_alternative
                                or walk_from_end >= walk_alternative
                                or (walk_to_start + walk_from_end) >= walk_alternative
                            ):
                                # if any one or the sum of both walking distances is larger than the alternative
                                # of walking the complete distance of the transport demand, then it's unlogical
                                # i.e. you are better off walking ;)
                                continue

                            # TODO: what if the combined duration of walking + driving + walking is longer than walking
                            # in this case, is transit really a viable alternative?

                            viable_transit.append(
                                {
                                    "vehicle": vehicle,
                                    "subroute": subroute,
                                    "initial_walking": walk_to_start,
                                    "final_walking": walk_from_end,
                                }
                            )

        return viable_transit

    def search_for_transportation_alternatives(  # noqa: D102
        self, transport_task: TransportRequest
    ) -> TransportationAlternativeBrowser:
        browser = TransportationAlternativeBrowser()
        search_time = transport_task.creation_time

        for viable_transit in self.find_viable_transit(
            transport_task,
            self._user_config.SPATIAL_STRATEGY,
            self._user_config.TRANSIT_MAX_WAIT,
        ):
            vehicle = viable_transit["vehicle"]
            subroute = viable_transit["subroute"]
            walking_dist_to_start = viable_transit["initial_walking"]
            walking_dist_to_destination = viable_transit["final_walking"]

            price = 0  # for PublicTransit we assume the perfect world
            distance = (
                subroute.total_distance()
                + walking_dist_to_start
                + walking_dist_to_destination
            )

            # from search to arrival + walk to final destination
            duration = SimulationTimeConverter.duration_between(
                SimulationTimeConverter.as_str(search_time),
                vehicle.prognose_arrival(subroute.destination),
            ) + (walking_dist_to_destination / self._user_config.WALKING_SPEED)

            # TODO: convenience=0 is only a placeholder
            transportation_alternative = TransportationAlternative(
                vehicle, subroute, price, duration, distance, 0
            )
            browser.add_transportation_alternative(transportation_alternative)

        return browser

    def _check_viable_stops(
        self,
        vehicle: PublicTransitVehicle,
        strategy: str,
        origin: GeodesicPosition,
        destination: GeodesicPosition,
    ) -> dict[str, list[Stop]]:
        """
        Find the route stops of a vehicle near the origin and near the destination.

        This checks only the spatial alignment, not the departure times.

        Parameters
        ----------
        vehicle : PublicTransitVehicle
            Vehicle whose route stops are checked.
        strategy : str
            Spatial strategy, only "hexagon" (a stop is near when it is in the same hexagon).
        origin : GeodesicPosition
            Origin of the transport request.
        destination : GeodesicPosition
            Destination of the transport request.

        Returns
        -------
        dict of str to list of Stop
            Stops near the origin under "origin" and stops near the destination under "destination".
            Empty if no stop is near the origin or no stop is near the destination.

        Raises
        ------
        NotImplementedError
            If the strategy is not "hexagon".
        """
        if strategy != "hexagon":
            raise NotImplementedError(
                "Other strategies for aligning travel demands are not implemented."
            )
        origin_region = origin.get_region_id()
        destination_region = destination.get_region_id()
        stops = vehicle.route.route_stops
        near_origin = [s for s in stops if s.get_region_id() == origin_region]
        near_destination = [s for s in stops if s.get_region_id() == destination_region]
        if not near_origin or not near_destination:
            return {}
        return {"origin": near_origin, "destination": near_destination}

    def _reachable_in_time(  # noqa: ANN202
        self,
        stop: Stop,
        vehicle: PublicTransitVehicle,
        current_time,  # noqa: ANN001
        current_position: GeodesicPosition,
        latest_departure,  # noqa: ANN001
    ):
        walking_dist = stop >> current_position
        # reachable within the specified temporal_lookahead and depart after arrival by foot
        reachable = (
            SimulationTimeConverter.as_str(
                current_time + (walking_dist / self._user_config.WALKING_SPEED)
            )
            <= vehicle.prognose_arrival(stop)
            <= latest_departure
        )
        return reachable, walking_dist
