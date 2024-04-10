import logging

from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.tasks.transport_task import TransportTask
from simulation.tasks.transportation_search_task import TransportationSearchTask


class SharedVehicleSearchEngine(SearchEngineInterface, PaymentInterface):
    def __init__(self, env):
        PaymentInterface.__init__(self)
        self._env = env
        self._fleet = None

    def search_for_transportation_alternatives(
        self, vehicle_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        """
        Spot all available vehicles to user
        :param vehicle_search_task:
        :return: Available Alternatives along with auxilary information regarding trip
        """
        browser = TransportationAlternativeBrowser()

        hexagon_origin = vehicle_search_task.agent_position.get_default_hexagon()

        (cars_in_area, scooters_in_area, kick_scooters_in_area, bikes_in_area) = (
            self.fleet.get_available_vehicles(hexagon_origin)
        )

        origin = vehicle_search_task.transport_task.origin
        destination = vehicle_search_task.transport_task.destination

        origin.get_default_hexagon()
        destination.get_default_hexagon()

        # Info about the route - if we distinguish between car/scooter and ks/bike routes, move to for loop
        # Calc Route
        route = Route(origin, destination)

        # Calc Distance
        distance = route.distance  # Euclidean Distance

        # Add all available cars to alternative browser
        for car in cars_in_area:
            # Calc Duration
            duration = distance / car.velocity

            # Calc Price
            price = duration * car.price_per_minute

            # Put together
            transportation_alternative = TransportationAlternative(
                car, route, price, duration, distance, 3
            )

            if car.has_enough_state_of_charge(distance):
                browser.add_transportation_alternative(transportation_alternative)

        # Add all available scooter to alternative browser
        for scooter in scooters_in_area:
            # Calc Duration
            duration = distance / scooter.velocity

            # Calc Price
            price = duration * scooter.price_per_minute

            # Put together
            transportation_alternative = TransportationAlternative(
                scooter, route, price, duration, distance, 2
            )

            if scooter.has_enough_state_of_charge(distance):
                browser.add_transportation_alternative(transportation_alternative)

        # Add all available kick scooter to alternative browser
        for kick_scooter in kick_scooters_in_area:
            # Calc Duration
            duration = distance / kick_scooter.velocity

            # Calc Price
            price = duration * kick_scooter.price_per_minute + 1.0  # 1€ Unlock Fee

            # Put together
            transportation_alternative = TransportationAlternative(
                kick_scooter, route, price, duration, distance, 1
            )

            if kick_scooter.has_enough_state_of_charge(distance):
                browser.add_transportation_alternative(transportation_alternative)

        return browser

    def pay_for_fulfilled_transportation_task(
        self,
        user,
        transportation_task: TransportTask,
        selected_transportation_alternative: TransportationAlternative,
    ):
        payment = selected_transportation_alternative.price
        self.increase_total_revenue(payment)

        # Add Transaction to Log
        self._transactions.append(
            {
                "origin": selected_transportation_alternative.route.origin.get_default_hexagon(),
                "destination": selected_transportation_alternative.route.destination.get_default_hexagon(),
                "time_start": transportation_task.time,
                "time_end": self._env.now,
                "price": selected_transportation_alternative.price,
                "distance": selected_transportation_alternative.distance,
                "duration": selected_transportation_alternative.duration,
                "energy_consumption": selected_transportation_alternative.energy_consumed,
                "selected_vehicle_mode": selected_transportation_alternative.vehicle.__class__.__name__,
                "state": "Fulfilled",
                **transportation_task.viable_vehicle_modes,
            }
        )

        logging.info(
            f"New Payment ({payment}) received from User {user.id}. Current Total Revenue: {self.total_revenue}.",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

    def withdraw_transportation_task(self, user, transportation_task: TransportTask):
        # Get available vehicle types
        vehicle_types = Configuration.instance().get_available_vehicle_types()

        # We assume an ordered list here (e.g., SharedCar, SharedScooter, SharedKickScooter)
        # We count the lost revenue for the "cheapest" mode
        for vehicle_type in vehicle_types:
            if (
                vehicle_type in transportation_task.viable_vehicle_modes
                and transportation_task.viable_vehicle_modes[vehicle_type] == 1
            ):
                distance = transportation_task.origin >> transportation_task.destination
                velocity = (
                    Configuration.instance().get_vehicle_config(vehicle_type).velocity
                )
                price_per_min = (
                    Configuration.instance()
                    .get_vehicle_config(vehicle_type)
                    .price_per_min
                )
                missed_trip_cost = distance / velocity * price_per_min

                if vehicle_type == "SharedKickScooter":
                    missed_trip_cost += 1.0  # Unlock Fee

        self.increase_total_missed_trips(missed_trip_cost)

        # Add Transaction to Log
        self._transactions.append(
            {
                "origin": transportation_task.origin.get_default_hexagon(),
                "destination": transportation_task.destination.get_default_hexagon(),
                "time_start": self._env.now,
                "time_end": self._env.now,
                "price": 0.0,
                "distance": transportation_task.origin
                >> transportation_task.destination,
                "duration": 0.0,
                "energy_consumption": 0.0,
                "selected_vehicle_mode": "None",
                "state": "Missed",
                **transportation_task.viable_vehicle_modes,
            }
        )

        logging.info(
            f"Missed trip of User {user.id}. Current Total Revenue: {self.total_revenue} - Total Trips: {self.total_fulfilled_trips} - Missed Trips {self.total_missed_trips}.",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )

    def register_fleet(self, fleet: VehicleFleet):
        self._fleet = fleet

    @property
    def fleet(self):
        if self._fleet:
            return self._fleet
        raise Exception(
            "Fleet was not registred. Inject fleet instance to search engine using register_fleet"
        )
