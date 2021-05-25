import logging

from simpy import Environment

from simulation.agent import user
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import VehicleAllocationEngineInterface
from simulation.operator.shared_vehicle_allocation_engine import SharedVehicleAllocationEngine
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
from simulation.tasks.transport_task import TransportTask


class World:

    def __init__(self, env: Environment,
                 search_engine: SearchEngineInterface,
                 payment_engine: PaymentInterface,
                 vehicle_assignment_engine: VehicleAllocationEngineInterface):
        self._env = env
        self._search_engine = search_engine # Allows users to search for vehicles
        self._payment_engine = payment_engine # Allows users to pay
        self._vehicle_assignment_engine = vehicle_assignment_engine # Allows vehicle allocations

        # Store all current users
        self._users = []

        self._user_limit = 10_000_000


    def add_user(self, origin, destination):
        """
            Add a user agent to the world with an origin and a destination.
        :param origin: Spatial Unit ID (e.g., hex_id)
        :param destination: Spatial Unit ID (e.g., hex_id)
        :return: None
        """
        if len(self._users) < self._user_limit:
            # Get Origin and Destination based on underlying environment
            geo_env = GeodesicEnvironment.getInstance()

            origin_lat, origin_lng = geo_env.get_random_position(origin)
            destination_lat, destination_lng = geo_env.get_random_position(destination)

            origin_position = GeodesicPosition(origin_lat, origin_lng)  # (Lat, Lng)
            destination_position = GeodesicPosition(destination_lat, destination_lng)  # (Lat, Lng)

            # Generate Transportation Task
            task = TransportTask(origin_position, destination_position)

            new_user = user.User(origin_position, task, self._search_engine, self._payment_engine, self._vehicle_assignment_engine, self._env)

            # Add user to user list
            self._users.append(new_user)

            # Start Process for each new user
            self._env.process(new_user.run())

            if len(self._users) == self._user_limit:
                logging.info(f'Reached User Limit of {self._user_limit}. Not adding more users to world.', extra={"clazz": self.__class__.__name__, "oid": " "})