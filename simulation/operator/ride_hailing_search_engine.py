from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative_ridehailing import TransportationAlternativeRideHailing
from simulation.operator.data_transfer_object.transportation_alternative_browser import TransportationAlternativeBrowser
from simulation.operator.interface.fleet_interface import FleetInterface
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.tasks.transport_task import TransportTask
from simulation.tasks.transportation_search_task import TransportationSearchTask

import logging
from line_profiler_pycharm import profile

class RideHailingSearchEngine(SearchEngineInterface, PaymentInterface):

    def __init__(self, env):
        PaymentInterface.__init__(self)
        self._env = env
        self._fleet = None
        self._driver_payment_share = Configuration.instance().get_driver_payment_share()
        self._AV_price_reduction = Configuration.instance().get_AV_price_reduction()

    @profile
    def search_for_transportation_alternatives(self, vehicle_search_task: TransportationSearchTask) -> TransportationAlternativeBrowser:
        """
        Spot all available vehicles to user
        :param vehicle_search_task:
        :return: Available Alternatives along with auxilary information regarding trip
        """
        browser = TransportationAlternativeBrowser()

        hexagon_origin = vehicle_search_task.agent_position.get_default_hexagon()

        origin = vehicle_search_task.transport_task.origin

        cars_in_area = self.fleet.get_available_vehicles_to_user(origin)

        destination = vehicle_search_task.transport_task.destination


        # Info about the route - if we distinguish between car/scooter and ks/bike routes, move to for loop
        # Calc Route
        route = Route(origin, destination)


        # Calc Distance
        distance = route.distance  # Euclidean Distance

        # Add all available cars to alternative browser
        AVs_in_area = [car for car in cars_in_area if car.__class__.__name__ == 'AutonomousCar']
        CVs_in_area = [car for car in cars_in_area if car.__class__.__name__ == 'RideHailingCar']
        if vehicle_search_task.transport_task.viable_vehicle_modes['RideHailingCar'] == 1:
            for car in CVs_in_area:
                # Calc waiting time
                route_to_pick_up = Route(car.position, origin)
                distance_to_pick_up = route_to_pick_up.distance

                # Calc Duration
                trip_duration = distance/car.velocity

                # Calc Price
                # TODO: hard_coded
                price = max(2 + trip_duration*car.price_per_minute + distance/1000 * 1.3, 5)


                # Put together
                transportation_alternative = TransportationAlternativeRideHailing(car, route, price, trip_duration, distance, 3, route_to_pick_up)

                total_distance = distance+distance_to_pick_up
                if car.has_enough_state_of_charge(total_distance):
                    browser.add_transportation_alternative(transportation_alternative)

        if vehicle_search_task.transport_task.viable_vehicle_modes['AutonomousCar'] == 1:
            for car in AVs_in_area:
                # Calc waiting time
                route_to_pick_up = Route(car.position, origin)
                distance_to_pick_up = route_to_pick_up.distance

                # Calc Duration
                trip_duration = distance / car.velocity

                # Calc Price
                # TODO: update the price for ride-hailing
                price = max(2 + trip_duration*car.price_per_minute + distance/1000 * 1.3, 5) * self._AV_price_reduction

                # Put together
                transportation_alternative = TransportationAlternativeRideHailing(car, route, price, trip_duration,
                                                                                  distance, 3, route_to_pick_up)

                total_distance = distance + distance_to_pick_up
                if car.has_enough_state_of_charge(total_distance):
                    browser.add_transportation_alternative(transportation_alternative)

        return browser

    def pay_for_fulfilled_transportation_task(self, user, transportation_task: TransportTask, selected_transportation_alternative: TransportationAlternativeRideHailing):
        payment = selected_transportation_alternative.price
        vehicle = selected_transportation_alternative.vehicle
        # we need to pay the driver costs
        if vehicle.__class__.__name__== 'RideHailingCar':
            self.increase_total_revenue(payment*(1-self._driver_payment_share))
            vehicle.update_earned_money(payment)

        else:
            self.increase_total_revenue(payment)


        # Add Transaction to Log
        self._transactions.append(
            {"origin": selected_transportation_alternative.route.origin.get_default_hexagon(),
             "destination": selected_transportation_alternative.route.destination.get_default_hexagon(),
             "time_start": transportation_task.time,
             "time_end": self._env.now,
             "price":selected_transportation_alternative.price,
             "distance": selected_transportation_alternative.distance,
             "duration":selected_transportation_alternative.duration,
             "energy_consumption": selected_transportation_alternative.energy_consumed,
             "waiting_time": selected_transportation_alternative.waiting_time,
             "pick_up_time": selected_transportation_alternative.pick_up_time,
             "selected_vehicle_mode": selected_transportation_alternative.vehicle.__class__.__name__ + '_' + str(selected_transportation_alternative.vehicle._electric_vehicle),
             "selected_vehicle_EV": selected_transportation_alternative.vehicle._electric_vehicle,
             "state":"Fulfilled", **transportation_task.viable_vehicle_modes}
        )

        logging.info(f"New Payment ({payment}) received from User {user.id}. Current Total Revenue: {self.total_revenue}.",
                      extra={"clazz": self.__class__.__name__, "oid": ""})

    def withdraw_transportation_task(self, user, transportation_task: TransportTask, state = None):
        # Get available vehicle types

        # We assume an ordered list here (e.g., SharedCar, SharedScooter, SharedKickScooter)
        # We count the lost revenue for the "cheapest" mode

        distance = transportation_task.origin >> transportation_task.destination
        #TODO: define price of the trip

        self.increase_total_missed_trips(1)

        # Add Transaction to Log
        self._transactions.append(
            {"origin": transportation_task.origin.get_default_hexagon(),
             "destination": transportation_task.destination.get_default_hexagon(),
             "time_start": self._env.now,
             "time_end": self._env.now,
             "price": 0.0,
             "distance": transportation_task.origin >> transportation_task.destination,
             "duration": 0.0,
             "energy_consumption": 0.0,
             "waiting_time": user._waiting_time,
             "pick_up_time": 0.0,
             "selected_vehicle_mode":"None",
             "selected_vehicle_EV": "None",
             "state": state, **transportation_task.viable_vehicle_modes}
        )

        logging.info(f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",
                      extra={"clazz": self.__class__.__name__, "oid": ""})

    def register_fleet(self, fleet: FleetInterface):
        self._fleet = fleet

    @property
    def fleet(self):
        if self._fleet:
            return self._fleet
        raise Exception("Fleet was not registred. Inject fleet instance to search engine using register_fleet")