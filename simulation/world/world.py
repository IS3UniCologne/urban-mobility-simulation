import logging

from numpy.random import normal
from simpy import Environment

from simulation.agent import user
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.operator.interface.payment_interface import PaymentInterface
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)
from simulation.tasks.transport_task import TransportTask
from simulation.vehicle.vehicle import Vehicle
from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics
from simulation.vehicle_choice_model.vehicle_choice_behavior_interface import (
    VehicleChoiceBehaviorInterface,
)
from simulation.world.population.PopulationFactory import PopulationFactory
from tracking.tracking import Tracking


class World:
    # There is only one instance of this class.
    __instance = None

    @staticmethod
    def instance() -> "World":
        """Static access method."""
        if World.__instance is None:
            raise Exception("World was not initialized")
        else:
            return World.__instance

    @staticmethod
    def init(
        env,
        search_engine,
        payment_engine,
        vehicle_assignment_engine,
        vehicle_choice_behavior,
        population_factory,
        charging_infrastructure,
        reset=False,
    ):
        """Static access method."""
        if World.__instance is None or reset is True:
            World(
                env,
                search_engine,
                payment_engine,
                vehicle_assignment_engine,
                vehicle_choice_behavior,
                population_factory,
                charging_infrastructure,
                reset,
            )
        return World.__instance

    def __init__(
        self,
        env: Environment,
        search_engine: SearchEngineInterface,
        payment_engine: PaymentInterface,
        vehicle_assignment_engine: VehicleAllocationEngineInterface,
        vehicle_choice_behavior: VehicleChoiceBehaviorInterface,
        population_factory: PopulationFactory,
        charging_infrastructure,
        reset: bool = False,
    ):
        """Virtually private constructor."""
        if World.__instance is not None and not reset:
            raise Exception("This class is a singleton!")
        else:
            World.__instance = self
            super(World, self).__init__()

        self._env = env
        self._search_engine = search_engine  # Allows users to search for vehicles
        self._payment_engine = payment_engine  # Allows users to pay
        self._vehicle_assignment_engine = (
            vehicle_assignment_engine  # Allows vehicle allocations
        )

        self._vehicle_choice_behavior = vehicle_choice_behavior

        self._demand_processes = []

        # Store all current users
        self._users = []
        self._user_processes = []

        # Store all current vehicles
        self._vehicles = []
        self._vehicle_processes = []

        # tracking
        self._tracking = Tracking.instance()

        # charging infra
        self._charging_infrastructure = charging_infrastructure

        # Config
        self._config = Configuration.instance()

        # Add Population Factory
        self._population_factory = population_factory

        # Events
        self._changed = self._env.event()

        self._user_limit = 10_000_000

    @property
    def user_processes(self):
        return self._user_processes

    @property
    def demand_processes(self):
        return self._demand_processes

    @property
    def vehicle_processes(self):
        return self._vehicle_processes

    def add_user(self, mode, fleet, origin, destination):
        """
        Add a user agent to the world with an origin and a destination.

        :param mode: which type of request
        :param fleet: which fleet
        :param origin: Spatial Unit ID (e.g., hex_id)
        :param destination: Spatial Unit ID (e.g., hex_id)
        :return: None
        """

        if len(self._users) < self._user_limit:
            # Get Origin and Destination based on underlying environment
            geo_env = GeodesicEnvironment.getInstance()

            origin_lat, origin_lng = geo_env.get_random_position(
                origin, f"hex_{self._config.spatial_resolution_value}"
            )
            destination_lat, destination_lng = geo_env.get_random_position(
                destination, f"hex_{self._config.spatial_resolution_value}"
            )

            origin_position = GeodesicPosition(
                origin_lat, origin_lng, origin
            )  # (Lat, Lng)
            destination_position = GeodesicPosition(
                destination_lat, destination_lng, destination
            )  # (Lat, Lng)

            # Vehicle Choice
            distance = origin_position >> destination_position
            tc = TripCharacteristics(distance)
            viable_vehicle_modes = self._vehicle_choice_behavior.choose_vehicle(tc)

            # Determine Consumer Type
            if mode == "public_transport":
                population_type = (
                    self._population_factory.generatePopulationTypeRideHailing()
                )

                # User Preferences
                max_wait_time = normal(
                    self._config.user_config.max_wait
                )  # sample from normal dist centered on config

                # Generate Transportation Task
                task = TransportTask(
                    self._env.now,
                    origin_position,
                    destination_position,
                    viable_vehicle_modes,
                    max_wait_time,
                )

                # new_user = user.TransitUser(origin_position, task, self._search_engine, self._payment_engine,
                #                             self._vehicle_assignment_engine, self._vehicle_choice_behavior, self._env,
                #                             passive=True if not self._config.transit_agent_config.dumb else False)
                new_user = user.TransitUser(
                    origin_position,
                    task,
                    self._search_engine,
                    self._payment_engine,
                    self._vehicle_assignment_engine,
                    self._vehicle_choice_behavior,
                    population_type,
                    self._env,
                    passive=True,
                )
            elif mode == "shared_vehicle":
                # Generate Transportation Task
                task = TransportTask(
                    self._env.now,
                    origin_position,
                    destination_position,
                    viable_vehicle_modes,
                )

                # Determine Consumer Type
                population_type = self._population_factory.generatePopulationType()

                new_user = user.User(
                    fleet,
                    origin_position,
                    task,
                    self._search_engine["shared_vehicle"],
                    self._payment_engine["shared_vehicle"],
                    self._vehicle_assignment_engine["shared_vehicle"],
                    self._vehicle_choice_behavior,
                    population_type,
                    self._env,
                )
                logging.debug(
                    f" Shared-vehicle user {new_user.user_id} starts searching for fleet {fleet} at {self._env.now}.",
                    extra={"clazz": self.__class__.__name__, "oid": " "},
                )
            elif mode == "ride_hailing":
                task = TransportTask(
                    self._env.now,
                    origin_position,
                    destination_position,
                    viable_vehicle_modes,
                )

                # Determine Consumer Type
                population_type = (
                    self._population_factory.generatePopulationTypeRideHailing()
                )

                new_user = user.RideHailingUser(
                    fleet,
                    origin_position,
                    task,
                    self._search_engine[f"ride_hailing_{fleet}"],
                    self._payment_engine[f"ride_hailing_{fleet}"],
                    self._vehicle_assignment_engine[f"ride_hailing_{fleet}"],
                    self._vehicle_choice_behavior,
                    population_type,
                    self._env,
                )
                logging.debug(
                    f"Ride-hailing user {new_user.user_id, population_type} request a vehicle at {self._env.now}.",
                    extra={"clazz": self.__class__.__name__, "oid": " "},
                )
            else:
                raise NotImplementedError('User mode "{mode}" not implemented.')

            # Add user to user list
            self._users.append(new_user)

            # register user with tracking
            new_user_uid = self._tracking.register(new_user)

            # Start Process for each new user
            self._user_processes.append(
                {"id": new_user.id, "proc": self._env.process(new_user.run())}
            )

            # Spawn cleanup process for that user
            self._env.process(self._cleanup_user(new_user, new_user_uid))

            if len(self._users) == self._user_limit:
                logging.info(
                    f"Reached User Limit of {self._user_limit}. Not adding more users to world.",
                    extra={"clazz": self.__class__.__name__, "oid": " "},
                )

    def _cleanup_user(self, user, user_uid):
        yield user.process_finished

        self._tracking.unregister_by_uid(user_uid)

    def add_vehicle(self, vehicle: Vehicle):
        self._vehicles.append(vehicle)

        # TODO: register vehicle with tracking

    def remove_vehicle(self, vehicle: Vehicle):
        self._vehicles.remove(vehicle)

        # TODO: de-register vehicle with tracking

    @property
    def users(self):
        return self._users

    @property
    def vehicles(self):
        return self._vehicles

    @property
    def charging_infrastructure(self):
        return self._charging_infrastructure

    @property
    def changed(self):
        return self._changed

    @changed.setter
    def changed(self, event):
        self._changed = event

    def stop_all_processes(self):
        # stop demand generation
        for d in self.demand_processes:
            try:
                d.interrupt()
            except RuntimeError:
                # already terminated
                pass

        # clean up user demands
        for u in self.user_processes:
            try:
                u["proc"].interrupt()
            except RuntimeError:
                # already terminated
                pass

    def user_process_by_id(self, user_id):
        procs = [p for p in self._user_processes if p["id"] == user_id]
        return procs[0]  # TODO: what about some error handling
