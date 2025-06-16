import logging

import simpy
from numpy.random import normal
from simpy import Environment

from simulation.agent import user
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.configuration.enums import (
    DailyResolution,
    SpatialResolution,
    TemporalResolution,
)
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
    __slots__ = (
        "_changed",
        "_charging_infrastructure",
        "_config",
        "_daily_resolution",
        "_demand_processes",
        "_env",
        "_payment_engine",
        "_population_factory",
        "_search_engine",
        "_simulation_finished",
        "_spatial_resolution",
        "_temporal_resolution",
        "_tracking",
        "_user_limit",
        "_user_processes",
        "_users",
        "_vehicle_assignment_engine",
        "_vehicle_choice_behavior",
        "_vehicle_processes",
        "_vehicles",
    )

    @staticmethod
    def instance() -> "World":
        """Static access method."""
        if World.__instance is None:
            raise Exception("World was not initialized")
        else:
            return World.__instance

    @staticmethod
    def init(  # noqa: ANN205
        env,  # noqa: ANN001
        search_engine,  # noqa: ANN001
        payment_engine,  # noqa: ANN001
        vehicle_assignment_engine,  # noqa: ANN001
        vehicle_choice_behavior,  # noqa: ANN001
        population_factory,  # noqa: ANN001
        charging_infrastructure,  # noqa: ANN001
        reset=False,  # noqa: ANN001
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

    def __init__(  # noqa: ANN204
        self,
        env: Environment,
        search_engine: SearchEngineInterface,
        payment_engine,  # noqa: ANN001
        vehicle_assignment_engine: VehicleAllocationEngineInterface,
        vehicle_choice_behavior: VehicleChoiceBehaviorInterface,
        population_factory: PopulationFactory,
        charging_infrastructure,  # noqa: ANN001
        reset: bool = False,
    ):
        """Virtually private constructor."""
        if World.__instance is not None and not reset:
            raise Exception("This class is a singleton!")
        else:
            World.__instance = self
            super(World, self).__init__()  # noqa: UP008

        self._config = Configuration()

        self._spatial_resolution: SpatialResolution = (
            self._config.world.SPATIAL_RESOLUTION
        )
        self._temporal_resolution: TemporalResolution = (
            self._config.world.TEMPORAL_RESOLUTION
        )

        self._daily_resolution: DailyResolution = self._config.world.DAILY_RESOLUTION

        self._env = env
        self._search_engine = search_engine  # Allows users to search for vehicles
        self._payment_engine = payment_engine  # Allows users to pay
        self._vehicle_assignment_engine = (
            vehicle_assignment_engine  # Allows vehicle allocations
        )

        self._vehicle_choice_behavior = vehicle_choice_behavior

        self._demand_processes = []

        # Store all current users
        self._users: set[user.User] = set()
        self._user_processes: dict[int, simpy.Process] = {}

        # Store all current vehicles
        self._vehicles: set[Vehicle] = set()
        self._vehicle_processes: dict[int, simpy.Process] = {}

        # TODO: keep track of fleets here as well

        # tracking
        self._tracking = Tracking.instance()

        # charging infra
        self._charging_infrastructure = charging_infrastructure

        # Config
        self._config = Configuration()

        # Add Population Factory
        self._population_factory = population_factory

        # Events
        self._changed = self._env.event()
        self._simulation_finished = self._env.event()

        self._user_limit = 10_000_000

    @property
    def spatial_resolution(self) -> SpatialResolution:
        """
        Get the spatial resolution of the world.

        Returns
        -------
        SpatialResolution
            The spatial resolution of the world, which is an instance of SpatialResolution.
        """
        return self._spatial_resolution

    @property
    def temporal_resolution(self) -> TemporalResolution:
        return self._temporal_resolution

    @property
    def daily_resolution(self) -> DailyResolution:
        return self._daily_resolution

    @property
    def user_processes(self):  # noqa: ANN201
        return self._user_processes

    @property
    def demand_processes(self):  # noqa: ANN201
        return self._demand_processes

    @property
    def vehicle_processes(self):  # noqa: ANN201
        return self._vehicle_processes

    def add_user(self, mode, fleet, origin, destination):  # noqa: ANN001, ANN201
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
                origin, f"hex_{self._config.world.SPATIAL_RESOLUTION_VALUE}"
            )
            destination_lat, destination_lng = geo_env.get_random_position(
                destination, f"hex_{self._config.world.SPATIAL_RESOLUTION_VALUE}"
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
                # User Preferences
                max_wait_time = normal(
                    self._config.user.TRANSIT_MAX_WAIT
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
                population_type = None

                new_user = user.TransitUser(
                    origin_position,
                    task,
                    self._search_engine,
                    self._payment_engine,
                    self._vehicle_assignment_engine,
                    self._vehicle_choice_behavior,
                    population_type,
                    self._env,
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
                    self._search_engine,
                    self._payment_engine,
                    self._vehicle_assignment_engine,
                    self._vehicle_choice_behavior,
                    population_type,
                    self._env,
                )
                logging.debug(
                    " Shared-vehicle user %s starts searching for fleet %s at %s.",
                    new_user.user_id,
                    fleet,
                    self._env.now,
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
                    "Ride-hailing user %s, %s request a vehicle at %s.",
                    new_user.user_id,
                    population_type,
                    self._env.now,
                    extra={"clazz": self.__class__.__name__, "oid": " "},
                )
            elif mode == "walking":
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
                    self._search_engine["walking"],
                    self._payment_engine["walking"],
                    self._vehicle_assignment_engine["walking"],
                    self._vehicle_choice_behavior,
                    population_type,
                    self._env,
                )
            else:
                raise NotImplementedError('User mode "{mode}" not implemented.')

            # Add user to user set
            self._users.add(new_user)
            # register user with tracking
            new_user_uid = self._tracking.register(new_user)

            # Start Process for each new user
            self._user_processes[new_user.id] = self._env.process(new_user.run())

            # Spawn cleanup process for that user
            self._env.process(self._cleanup_user(new_user, new_user_uid))

            if len(self._users) == self._user_limit:
                logging.info(
                    "Reached User Limit of %s. Not adding more users to world.",
                    self._user_limit,
                    extra={"clazz": self.__class__.__name__, "oid": " "},
                )

    def _cleanup_user(self, user, user_uid: str):  # noqa: ANN001, ANN202
        """
        Wait for the user process to finish, then remove the user from the simulation.

        Parameters
        ----------
        user : User or subclass
            The user agent to clean up.
        user_uid : str
            The unique identifier for tracking.
        """
        yield user.process_finished

        # Remove user from tracking
        self._tracking.unregister_by_uid(user_uid)

        # Remove user from self._users
        self._users.discard(user)

        # Remove user process from self._user_processes
        if user.id in self._user_processes:
            del self._user_processes[user.id]

        logging.debug(
            "User %s removed from simulation after process finished.",
            user.id,
            extra={"clazz": self.__class__.__name__, "oid": " "},
        )

    def add_vehicle(self, vehicle: Vehicle):  # noqa: ANN201
        self._vehicles.add(vehicle)

        # TODO: register vehicle with tracking

    def remove_vehicle(self, vehicle: Vehicle):  # noqa: ANN201
        self._vehicles.discard(vehicle)

        # TODO: de-register vehicle with tracking

    @property
    def users(self):  # noqa: ANN201
        return self._users

    @property
    def vehicles(self):  # noqa: ANN201
        return self._vehicles

    @property
    def charging_infrastructure(self):  # noqa: ANN201
        return self._charging_infrastructure

    @property
    def simulation_finished(self):  # noqa: ANN201
        return self._simulation_finished

    @property
    def changed(self):  # noqa: ANN201
        return self._changed

    @changed.setter
    def changed(self, event):  # noqa: ANN001, ANN202
        self._changed = event

    def stop_all_processes(self):  # noqa: ANN201
        # stop demand generation
        for d in self.demand_processes:
            try:
                d.interrupt()
            except RuntimeError:
                # already terminated
                pass

        # clean up user demands
        for process in self.user_processes.values():
            try:
                process.interrupt()
            except RuntimeError:
                # already terminated
                pass

    def user_process_by_id(self, user_id):  # noqa: ANN001, ANN201
        return self._user_processes.get(user_id)  # returns the process or None
