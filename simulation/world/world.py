import logging

import simpy
from numpy.random import normal
from simpy import Environment

import simulation.agent.user as user
from simulation.helper.configuration.configuration import Configuration
from simulation.vehicle.vehicle import Vehicle
from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics
from simulation.vehicle_choice_model.vehicle_choice_behavior_interface import VehicleChoiceBehaviorInterface
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import VehicleAllocationEngineInterface
from simulation.tasks.transport_task import TransportTask


class World:
    # There is only one instance of this class.
    __instance = None

    @staticmethod
    def instance() -> 'World':
        """ Static access method. """
        if World.__instance is None:
            raise Exception("World was not initialized")
        else:
            return World.__instance

    @staticmethod
    def init(env, search_engine, payment_engine, vehicle_assignment_engine, vehicle_choice_behavior, reset=False):
        """ Static access method. """
        if World.__instance is None or reset is True:
            World(env, search_engine, payment_engine, vehicle_assignment_engine, vehicle_choice_behavior, reset)
        return World.__instance

    def __init__(self, env: Environment,
                 search_engine: SearchEngineInterface,
                 payment_engine: PaymentInterface,
                 vehicle_assignment_engine: VehicleAllocationEngineInterface,
                 vehicle_choice_behavior: VehicleChoiceBehaviorInterface,
                 reset: bool = False):
        """ Virtually private constructor. """
        if World.__instance is not None and not reset:
            raise Exception("This class is a singleton!")
        else:
            World.__instance = self
            super(World, self).__init__()

        self._env = env
        self._search_engine = search_engine  # Allows users to search for vehicles
        self._payment_engine = payment_engine  # Allows users to pay
        self._vehicle_assignment_engine = vehicle_assignment_engine  # Allows vehicle allocations

        self._vehicle_choice_behavior = vehicle_choice_behavior

        self._demand_processes = []

        # Store all current users
        self._users = []
        self._user_processes = []

        # Store all current vehicles
        self._vehicles = []

        # Config
        self._config = Configuration.instance()

        # Events
        self._changed = self._env.event()

        self._user_limit = 10_000_000

    @property
    def user_processes(self):
        return self._user_processes

    @property
    def demand_processes(self):
        return self._demand_processes


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

            origin_lat, origin_lng = geo_env.get_random_position(origin, f'hex_{self._config.spatial_resolution_value}')
            destination_lat, destination_lng = geo_env \
                .get_random_position(destination, f'hex_{self._config.spatial_resolution_value}')

            origin_position = GeodesicPosition(origin_lat, origin_lng, origin)  # (Lat, Lng)
            destination_position = GeodesicPosition(destination_lat, destination_lng, destination)  # (Lat, Lng)

            # Vehicle Choice
            distance = origin_position >> destination_position
            tc = TripCharacteristics(distance)
            viable_vehicle_modes = self._vehicle_choice_behavior.choose_vehicle(tc)

            if self._vehicle_choice_behavior.__class__.__name__ == 'PublicTransitVehicleChoiceBehavior':
                # User Preferences
                max_wait_time = normal(self._config.user_config.max_wait)  # sample from normal dist centered on config

                # Generate Transportation Task
                task = TransportTask(self._env.now, origin_position, destination_position, viable_vehicle_modes,
                                     max_wait_time)

                new_user = user.TransitUser(origin_position, task, self._search_engine, self._payment_engine,
                                            self._vehicle_assignment_engine, self._vehicle_choice_behavior, self._env,
                                            passive=True)
            else:
                # Generate Transportation Task
                task = TransportTask(self._env.now, origin_position, destination_position, viable_vehicle_modes)

                new_user = user.User(origin_position, task, self._search_engine, self._payment_engine,
                                     self._vehicle_assignment_engine, self._vehicle_choice_behavior, self._env)

            # Add user to user list
            self._users.append(new_user)

            # Start Process for each new user
            self._user_processes.append(self._env.process(new_user.run()))

            if len(self._users) == self._user_limit:
                logging.info(f'Reached User Limit of {self._user_limit}. Not adding more users to world.',
                             extra={"clazz": self.__class__.__name__, "oid": " "})

    def add_vehicle(self, vehicle: Vehicle):
        self._vehicles.append(vehicle)

    def remove_vehicle(self, vehicle: Vehicle):
        self._vehicles.remove(vehicle)

    @property
    def users(self):
        return self._users

    @property
    def vehicles(self):
        return self._vehicles

    @property
    def changed(self):
        return self._changed

    @changed.setter
    def changed(self, event):
        self._changed = event
