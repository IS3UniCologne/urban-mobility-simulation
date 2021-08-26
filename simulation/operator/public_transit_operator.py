import logging
import pandas as pd
import geopandas as gpd

from simpy import Environment

from simulation.helper.configuration.configuration import Configuration, TemporalBucket, SpatialResolution
from simulation.infrastructure.helper.timetable import Timetable
from simulation.helper.time import SimulationTime, SimulationTimeConverter
from simulation.operator.data_transfer_object.transportation_alternative import TransportationAlternative
from simulation.operator.data_transfer_object.transportation_alternative_browser import TransportationAlternativeBrowser
from simulation.operator.data_transfer_object.vehicle_allocation import VehicleAllocation
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import VehicleAllocationEngineInterface
from simulation.tasks.transport_task import TransportTask
from simulation.tasks.transportation_search_task import TransportationSearchTask
from simulation.vehicle.public_transit_bus import Bus
from simulation.infrastructure.route import PublicTransitRoute
from simulation.infrastructure.transit_network.stop import Stop
from simulation.infrastructure.transit_network.route_segment import RouteSegment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle


class PublicTransitOperator(SearchEngineInterface, VehicleAllocationEngineInterface, PaymentInterface):
    def __init__(self, env: Environment, timetable: Timetable):
        PaymentInterface.__init__(self)
        self._timetable = timetable
        self._env = env
        self._time = SimulationTime(env)
        self._busses = []

        # Events
        self._vehicles_assigned_to_users = self._env.event()

        # Config
        self._config = Configuration.instance()

        self._operator_process = self._env.process(self._run())

    def _run(self):
        """
        TransitOperator Lifecycle
        """
        while True:
            logging.debug(f'TransitOperator is at time {self._time.now_as_str()}',
                          extra={"clazz": self.__class__.__name__, "oid": ""})

            trips = self._timetable.next_trips(self._time)

            if trips:  # non-empty list is True
                for trip_id in trips:
                    trip = self._timetable.trip_by_id(trip_id)
                    route = self._build_route(trip)
                    self._busses.append(self._spawn_bus(route))

            yield self._env.timeout(1)

    def search_for_transportation_alternatives(self,
                                               transportation_search_task: TransportationSearchTask) -> TransportationAlternativeBrowser:

        browser = TransportationAlternativeBrowser()
        search_time = transportation_search_task.transport_task.time

        for viable_transit in self._find_viable_transit(transportation_search_task, 'hexagon', 10):
            vehicle = viable_transit['vehicle']
            subroute = viable_transit['subroute']
            walking_dist_to_start = viable_transit['initial_walking']
            walking_dist_to_destination = viable_transit['final_walking']

            price = 0  # for PublicTransit we assume the perfect world
            distance = subroute.total_distance() + walking_dist_to_start + walking_dist_to_destination

            # from search to arrival + walk to final destination
            duration = SimulationTimeConverter.duration_between(SimulationTimeConverter.as_str(search_time),
                                                                vehicle.prognose_arrival(subroute.destination)) + \
                                                               (walking_dist_to_destination / 83.33)

            transportation_alternative = TransportationAlternative(vehicle, subroute, price, duration, distance)
            browser.add_transportation_alternative(transportation_alternative)

        return browser

    def request_vehicle_allocation(self, user,
                                   selected_transportation_alternative: TransportationAlternative) -> VehicleAllocation:
        """
        In case of public transit allocate each request succesfully as long as the vehicle has available seats
        :param user:
        :param selected_transportation_alternative:
        :return:
        """
        selected_vehicle = selected_transportation_alternative.vehicle

        yield self._env.timeout(.01) # TODO: this is just hacking around the expected generator

        if selected_vehicle.available_seats > 0:
            return VehicleAllocation(user, selected_vehicle, selected_transportation_alternative,
                                     selected_vehicle.position, selected_transportation_alternative)
        else:
            return None

    def notify_user_arrival_at_pick_up_position(self, vehicle_assignment: VehicleAllocation):

        # TODO: needed?
        pass

    def pay_for_fulfilled_transportation_task(self, user, transportation_task: TransportTask,
                                              selected_transportation_alternative: TransportationAlternative):

        # TODO: move to PaymentInterface?
        payment = selected_transportation_alternative.price
        self.increase_total_revenue(payment)

        # Add Transaction to Log
        self._transactions.append(
            {"origin": selected_transportation_alternative.route.origin.get_hexagon(),
             "destination": selected_transportation_alternative.route.destination.get_hexagon(),
             "time_start": transportation_task.time,
             "time_end": self._env.now,
             "price":selected_transportation_alternative.price,
             "distance": selected_transportation_alternative.distance,
             "duration":selected_transportation_alternative.duration,
             "selected_vehicle_mode":selected_transportation_alternative.vehicle.__class__.__name__,
             "state":"Fulfilled", **transportation_task.viable_vehicle_modes}
        )

        logging.info(f"New Payment ({payment}) received from User {user.id}. Current Total Revenue: {self.total_revenue}.",
                     extra={"clazz": self.__class__.__name__, "oid": ""})

    def withdraw_transportation_task(self, user, transportation_task: TransportTask):
        self.increase_total_missed_trips()

        # Add Transaction to Log
        self._transactions.append(
            {"origin": transportation_task.origin.get_hexagon(),
             "destination": transportation_task.destination.get_hexagon(),
             "time_start": self._env.now,
             "time_end": self._env.now,
             "price": 0.0,
             "distance": transportation_task.origin >> transportation_task.destination,
             "duration": 0.0,
             "selected_vehicle_mode":"None",
             "state":"Missed", **transportation_task.viable_vehicle_modes}
        )

        logging.info(f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",
                     extra={"clazz": self.__class__.__name__, "oid": ""})

    def _build_route(self, trip: pd.DataFrame) -> PublicTransitRoute:
        origin_row = trip.iloc[0]
        destination_row = trip.iloc[-1]

        origin = Stop(0, origin_row['stop_id'], origin_row['stop_lat'], origin_row['stop_lon'],
                      origin_row['departure_time'], origin_row['dep_next_day'])
        destination = Stop(len(trip.index) - 1, destination_row['stop_id'], destination_row['stop_lat'],
                           destination_row['stop_lon'], destination_row['departure_time'],
                           destination_row['dep_next_day'])

        route_id = origin_row['route_id']
        trip_id = origin_row['trip_id']

        # create route prototype with OD and add first stop
        route = PublicTransitRoute(origin, destination, route_id, trip_id)
        route.add_route_stop(origin)

        last_stop = origin
        total_traveled = 0

        # skip origin as it is already added
        for stop_id, row in enumerate(trip[1:].itertuples(index=False), start=1):
            stop = Stop(stop_id, row.stop_id, row.stop_lat, row.stop_lon, row.departure_time, row.dep_next_day)
            # Actual distance traveled along the associated shape, from the first stop to the stop specified in this record
            distance = row.shape_dist_traveled - total_traveled

            route_segment = RouteSegment(stop_id - 1, last_stop, stop, distance)

            # add route segment and next stop
            route.add_route_segment(route_segment)
            route.add_route_stop(stop)

            last_stop = stop
            total_traveled += distance

        return route

    def _spawn_bus(self, route: PublicTransitRoute):
        init_position = GeodesicPosition(*route.origin.getExactLocation())
        bus = Bus(self._env, route, init_position)
        bus.current_stop = route.origin  # TODO: move to Bus/PublicTransitVehicle?
        return bus

    def _find_viable_transit(self, transportation_search_task, spatial_strategy='hexagon', temporal_lookahead=10):
        search_time = transportation_search_task.transport_task.time
        latest_departure = SimulationTimeConverter.as_str(search_time + temporal_lookahead)
        walk_alternative = transportation_search_task.transport_task.origin >> transportation_search_task.transport_task.destination

        viable_transit = []

        if not self._busses:
            # No busses are en-route, report no viable alternative
            # TODO: fallback to planned timetable - a new bus could spawn within temporal_lookahead?
            return viable_transit

        for vehicle in self._busses:
            viable_stops = self._check_viable_stops(vehicle, spatial_strategy,
                                                    transportation_search_task.transport_task.origin,
                                                    transportation_search_task.transport_task.destination)
            if viable_stops:
                # check for temporal alignment
                reachable_stops = []
                for stop in viable_stops['origin']:
                    reachable, distance = self._reachable(stop, vehicle, search_time,
                                                          transportation_search_task.transport_task.origin,
                                                          latest_departure)
                    if reachable:
                        reachable_stops.append((stop, distance)) # tuple of (Stop, walking distance to/from)

                if reachable_stops:
                    logging.debug(f'Bus {vehicle.id} is a viable transport alternative from '
                                  f'{transportation_search_task.transport_task.origin} to '
                                  f'{transportation_search_task.transport_task.destination}!',
                                  extra={"clazz": self.__class__.__name__, "oid": ""})

                    # build all possible combinations of viable subroutes
                    for start, walk_to_start in reachable_stops:
                        for end in viable_stops['destination']:
                            if start.stop_id >= end.stop_id:
                                # only look at travel in the right direction
                                continue

                            subroute = vehicle.route.subroute(start, end)
                            walk_from_end = end >> transportation_search_task.transport_task.destination

                            if walk_to_start >= walk_alternative or walk_from_end >= walk_alternative or (walk_to_start + walk_from_end) >= walk_alternative:
                                # if any one or the sum of both walking distances is larger than the alternative
                                # of walking the complete distance of the transport demand, then it's unlogical
                                # i.e. you are better off walking ;)
                                continue

                            # TODO: what if the combined duration of walking + driving + walking is longer than walking
                            # in this case, is transit really a viable alternative?

                            viable_transit.append({'vehicle': vehicle,
                                                   'subroute': subroute,
                                                   'initial_walking': walk_to_start,
                                                   'final_walking': walk_from_end}
                                                  )

        return viable_transit

    @staticmethod
    def _check_viable_stops(vehicle: PublicTransitVehicle, strategy, origin: GeodesicPosition,
                            destination: GeodesicPosition):
        """
        Check for viable transit stops nearby origin - destination travel demand for a given vehicle
        This only checks spatial alignment
        :param vehicle: PublicTransitVehicle
        :param strategy: e.g. 'hexagon' (viable when in same hexagon), 'euclidean' (viable when eucl. dist. <= X), ...
        :param origin: GeodesicPosition
        :param destination: GeodesicPosition
        :return: dict
        """

        if strategy == 'hexagon':
            # trips are viable that start/end in the same hexagon as origin and destination
            origin_hex, origin_poly = origin.get_hexagon()
            destination_hex, destination_poly = destination.get_hexagon()
            in_vicinity = [{'origin': x.is_in_geometry(origin_poly), 'destination': x.is_in_geometry(destination_poly)}
                           for x in vehicle.route.route_stops]
            origin_in_vicinity_at = [ix for ix, element in enumerate(in_vicinity) if element['origin']]
            destination_in_vicinity_at = [ix for ix, element in enumerate(in_vicinity) if element['destination']]

            # now we know which stops would potentially be in vicinity of each origin and destination
            if not origin_in_vicinity_at or not destination_in_vicinity_at:
                # if either no stop is in vicinity for origin or destination, return no viable stops
                return {}
            else:
                # otherwise return a dict of viable stops for origin and destination
                return {'origin': [vehicle.route.route_stop_by_id(ix) for ix in origin_in_vicinity_at],
                        'destination': [vehicle.route.route_stop_by_id(ix) for ix in destination_in_vicinity_at]}
        else:
            raise NotImplementedError(f'Other strategies for aligning travel demands are not implemented.')

    @staticmethod
    def _reachable(stop: Stop, vehicle: PublicTransitVehicle, current_time, current_position: GeodesicPosition,
                   latest_departure):
        walking_dist = stop >> current_position
        # reachable within the specified temporal_lookahead and depart after arrival by foot
        reachable = SimulationTimeConverter.as_str(current_time + (walking_dist / 83.33)) <= \
                    vehicle.prognose_arrival(stop) <= \
                    latest_departure
        return reachable, walking_dist
