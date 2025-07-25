from __future__ import annotations

import os
from typing import TYPE_CHECKING

from numpy.random import normal

from simulation.agent import user
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.enums import AutonomyType, VehicleType
from simulation.helper.simulation_base import SimulationBase
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.operator.fleet_factory import (
    generate_mixed_fleet,
    generate_mixed_ride_hailing_fleet,
)
from simulation.operator.operations_management.integrated_shared_mobility_operations import (
    IntegratedSharedMobilityOperations,
)
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.operator.public_transport_allocation_engine import (
    PublicTransportAllocationEngine,
)
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_operator import RideHailingOperator
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.operator.shared_mobility_operator import SharedMobilityOperator
from simulation.operator.shared_vehicle_allocation_engine import (
    SharedVehicleAllocationEngine,
)
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
from simulation.tasks.transport_task import TransportTask
from simulation.vehicle_choice_model.distance_based_shared_vehicle_choice_behavior import (
    DistanceBasedSharedVehicleVehicleChoiceBehavior,
)
from simulation.vehicle_choice_model.only_car_vehicle_choice_behavior import (
    OnlyCarVehicleChoiceBehavior,
)
from simulation.vehicle_choice_model.trip_characteristics import TripCharacteristics
from simulation.world.population.PopulationFactory import PopulationFactory

if TYPE_CHECKING:
    import simpy
    from pandas import DataFrame

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_environment import GeodesicEnvironment
    from simulation.helper.configuration.configuration import Configuration
    from simulation.helper.random.random_manager import RandomManager
    from simulation.infrastructure.helper.timetable import Timetable
    from simulation.operator.interface.vehicle_allocation_engine_interface import (
        VehicleAllocationEngineInterface,
    )
    from simulation.operator.operations_management.operations_public_transport import (
        OperationsPublicTransport,
    )
    from simulation.operator.operator import Operator
    from simulation.operator.public_transit_operator import PublicTransitOperator
    from simulation.operator.public_transport_search_engine import (
        PublicTransportSearchEngine,
    )
    from simulation.operator.public_transport_vehicle_fleet import (
        PublicTransportVehicleFleet,
    )
    from simulation.vehicle.vehicle import Vehicle


class World(SimulationBase):
    # There is only one instance of this class.
    __instance = None
    __slots__ = (
        "_changed",
        "_charging_infrastructure",
        "_config",
        "_daily_resolution",
        "_demand_processes",
        "_distance_matrix",
        "_env",
        "_geo_env",
        "_operators",
        "_payment_engine",
        "_population_factory",
        "_random_manager",
        "_search_engine",
        "_sim",
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

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._sim: SimulationContext = sim
        self._config: Configuration = sim.config
        self._geo_env: GeodesicEnvironment = sim.geo_env
        self._env: simpy.Environment = sim.env
        self._random_manager = sim.random_manager
        self._vehicle_assignment_engine: dict[
            str, VehicleAllocationEngineInterface
        ] = {}

        self._distance_matrix: DataFrame = self._load_distance_matrix()

        self._operators: list[Operator] = []

        self._setup_vehicle_choice_behavior()

        self._demand_processes = []

        self._search_engine = {}
        self._payment_engine = {}

        # Store all current users
        self._users: set[user.User] = set()
        self._user_processes: dict[int, simpy.Process] = {}

        # Store all current vehicles
        # TODO: This is not being set correctly. Do we even want this here ?
        self._vehicles: set[Vehicle] = set()
        self._vehicle_processes: dict[int, simpy.Process] = {}

        # TODO: keep track of fleets here as well

        # Add Population Factory
        self._population_factory: PopulationFactory | None = (
            self._initialize_population_factory()
        )

        self._setup_operators()

        # Events
        self._changed = self._env.event()
        self._simulation_finished = self._env.event()

        self._user_limit = 10_000_000

    @property
    def random_manager(self) -> RandomManager:
        """Get the random manager."""
        return self._random_manager

    @property
    def geo_env(self) -> GeodesicEnvironment:
        return self._geo_env

    @property
    def user_processes(self):  # noqa: ANN201
        return self._user_processes

    @property
    def demand_processes(self):  # noqa: ANN201
        return self._demand_processes

    @property
    def vehicle_processes(self):  # noqa: ANN201
        return self._vehicle_processes

    @property
    def operators(self) -> list[Operator]:
        """Get a list of operators in the world."""
        return self._operators

    def _setup_vehicle_choice_behavior(self) -> None:
        if self._config.ride_hailing_operators:
            rh_modes: list[str] = [AutonomyType.AUTONOMOUS, AutonomyType.HUMAN_DRIVEN]
            self._vehicle_choice_behavior = OnlyCarVehicleChoiceBehavior(rh_modes)

        elif self._config.shared_vehicle_operators:
            shared_modes: list[VehicleType] = list(self._config.shared_vehicles.keys())

            self._vehicle_choice_behavior = DistanceBasedSharedVehicleVehicleChoiceBehavior(
                path_to_choice_model=self._config.path.PATH_TO_MODE_CHOICE_MODEL,
                substitution_boundary=self._config.mode_choice_model.SUBSTITUTION_BOUNDARY,
                available_vehicles=shared_modes,
            )

        elif self._config.transit_operators:
            from simulation.vehicle_choice_model.public_transit_vehicle_choice_behavior import (
                PublicTransitVehicleChoiceBehavior,
            )

            self._vehicle_choice_behavior = PublicTransitVehicleChoiceBehavior(["Bus"])

    def _initialize_charging_infrastructure(self) -> ChargingInfrastructure | None:
        # TODO: This is currently completely ignored by shared vehicle operators, while ridehailing operators all use the same charging infrastructure.
        # This probably needs some refactoring depending on what we want to do with charging infrastructure in the future.

        if hasattr(self._config, "charging_infrastructure"):
            return ChargingInfrastructure.init(
                sim=self._sim,
                location_list=self._config.charging_infrastructure.LOCATIONS,
                power_list=self._config.charging_infrastructure.CHARGING_STATION_POWER,
                capacity_list=self._config.charging_infrastructure.CHARGING_STATION_CAPACITY,
                queue_size=self._config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE,
                reset=True,
            )
        else:
            return None

    def _initialize_population_factory(self) -> PopulationFactory | None:
        if hasattr(self._config, "population"):
            if self._config.population.RIDE_HAILING_POPULATION_PROBABILITIES:
                return PopulationFactory(
                    prob=self._config.population.RIDE_HAILING_POPULATION_PROBABILITIES,
                    random_manager=self._random_manager,
                )
            elif self._config.population.SHARED_VEHICLE_POPULATION_PROBABILITIES:
                return PopulationFactory(
                    prob=self._config.population.SHARED_VEHICLE_POPULATION_PROBABILITIES,
                    random_manager=self._random_manager,
                )
            elif (
                hasattr(self._config.population, "TRANSIT_POPULATION_PROBABILITIES")
                and self._config.population.TRANSIT_POPULATION_PROBABILITIES
            ):
                return PopulationFactory(
                    prob=self._config.population.TRANSIT_POPULATION_PROBABILITIES,
                    random_manager=self._random_manager,
                )
            else:
                return None
        else:
            return None

    def _setup_operators(self) -> None:
        self._setup_ride_hailing_operators()
        self._setup_shared_vehicle_operators()
        self._setup_transit_operators()

    def _setup_transit_operators(self) -> None:
        if not self._config.transit_operators:
            return

        timetable: Timetable = self._load_timetable()

        for i, operator_cfg in enumerate(self._config.transit_operators):
            operator_id = f"public_transport_{i}"
            self.logger.info("Setting up public transport operator %s", operator_id)

            fleet = self._initialize_public_transport_fleet()
            search_engine = self._create_public_transport_search_engine(
                operator_cfg, fleet
            )
            allocation_engine = PublicTransportAllocationEngine(self._sim)
            operations = self._create_public_transport_operations(
                operator_cfg, timetable, fleet
            )

            operator = self._create_public_transit_operator(
                fleet, operations, search_engine, allocation_engine
            )

            self._search_engine[operator_id] = search_engine
            self._payment_engine[operator_id] = operator
            self._vehicle_assignment_engine[operator_id] = allocation_engine

            self._operators.append(operator)

    def _setup_shared_vehicle_operators(self) -> None:
        for i, operator_cfg in enumerate(self._config.shared_vehicle_operators):
            operator_id = f"shared_vehicle_{i}"

            self._search_engine[operator_id] = SharedVehicleSearchEngine(sim=self._sim)
            self._vehicle_assignment_engine[operator_id] = (
                SharedVehicleAllocationEngine(sim=self._sim)
            )

            fleet = generate_mixed_fleet(sim=self._sim, world=self)
            self._search_engine[operator_id].register_fleet(fleet)

            ordered_available_vehicle_types = fleet.vehicle_types

            ordered_max_vehicle_supply = [
                fleet.count_by_type[veh_type]
                for veh_type in ordered_available_vehicle_types
            ]

            # TODO: Ordered vehicle modes are silly, it should not work like that. Maybe enums ?Why do we need these mode lists at all ?
            operations = IntegratedSharedMobilityOperations(
                sim=self._sim,
                time_between_operations=operator_cfg.OPERATIONS_START,
                operation_duration=operator_cfg.OPERATIONS_DURATION,
                distance_matrix=self._distance_matrix,
                ordered_available_vehicle_types=ordered_available_vehicle_types,
                ordered_max_vehicle_supply=ordered_max_vehicle_supply,
                state_of_charge_threshold=operator_cfg.RECHARGE_THRESHOLD,
                base_regions=operator_cfg.BASE_REGIONS,
                base_capacity=operator_cfg.BASE_CAPACITY,
            )

            operator = SharedMobilityOperator(
                sim=self._sim,
                fleet=fleet,
                charging_infrastructure=None,
                operations=operations,
                search_engine=self._search_engine[operator_id],
                allocation_engine=self._vehicle_assignment_engine[operator_id],
                number_service_workers=operator_cfg.NUMBER_OF_SERVICE_WORKERS,
            )
            self.operators.append(operator)
            self._payment_engine[operator_id] = operator

    def _load_distance_matrix(self) -> None:
        hexagons = self.geo_env.getLayer(
            f"hex_{self._config.world.SPATIAL_RESOLUTION}"
        ).index.tolist()

        # TODO: Remove hardcoded path
        dmi = DistanceMatrixImporter(
            hexagons,
            self._config.world.SPATIAL_RESOLUTION,
            os.path.normpath(os.path.join(".", "data", "infrastructure")),
            self._config.world.CITY,
        )
        return dmi.load_distance_matrix()

    def _setup_ride_hailing_operators(self) -> None:
        self._charging_infrastructure: ChargingInfrastructure | None = (
            self._initialize_charging_infrastructure()
        )

        rh_ops = self._config.ride_hailing_operators
        num_rh_ops = max(2, len(rh_ops)) if rh_ops else 0
        for i in range(num_rh_ops):
            operator_cfg = rh_ops[min(i, len(rh_ops) - 1)]

            operator_id = f"ride_hailing_{i}"
            self._search_engine[operator_id] = RideHailingSearchEngine(sim=self._sim)
            self._vehicle_assignment_engine[operator_id] = RideHailingAllocationEngine(
                sim=self._sim
            )
            fleet = generate_mixed_ride_hailing_fleet(sim=self._sim, world=self)
            self._search_engine[operator_id].register_fleet(fleet)
            allow_queue = (
                sum(self._config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE)
                > 0
            )
            # TODO
            available_vehicle_modes = [
                AutonomyType.AUTONOMOUS,
                AutonomyType.HUMAN_DRIVEN,
            ]
            available_vehicle_modes_supply = [
                self._config.ride_hailing_global.N_RIDE_HAILING_CARS,
                self._config.ride_hailing_global.N_AUTONOMOUS_CARS,
            ]
            operations = RideHailingBaseChargingOperations(
                sim=self._sim,
                distance_matrix=self._distance_matrix,
                time_between_operations=operator_cfg.OPERATIONS_START,
                operation_duration=operator_cfg.OPERATIONS_DURATION,
                available_modes=available_vehicle_modes,
                available_modes_supply=available_vehicle_modes_supply,
                state_of_charge_threshold=operator_cfg.RECHARGE_THRESHOLD,
                allow_queue=allow_queue,
                world=self,
            )
            operator = RideHailingOperator(
                sim=self._sim,
                fleet=fleet,
                charging_infrastructure=self.charging_infrastructure,
                operations=operations,
                search_engine=self._search_engine[operator_id],
                allocation_engine=self._vehicle_assignment_engine[operator_id],
            )
            self._operators.append(operator)
            self._payment_engine[operator_id] = operator

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

            # TODO: Why are we doing this here ??
            origin_lat, origin_lng = self._geo_env.get_random_position(
                origin, f"hex_{self._config.world.SPATIAL_RESOLUTION}"
            )
            destination_lat, destination_lng = self._geo_env.get_random_position(
                destination, f"hex_{self._config.world.SPATIAL_RESOLUTION}"
            )

            origin_position = GeodesicPosition(
                self._sim, origin_lat, origin_lng, origin
            )  # (Lat, Lng)
            destination_position = GeodesicPosition(
                self._sim, destination_lat, destination_lng, destination
            )  # (Lat, Lng)

            # Vehicle Choice
            distance = origin_position >> destination_position
            tc = TripCharacteristics(distance)
            viable_vehicle_types = self._vehicle_choice_behavior.choose_vehicle(tc)

            # Determine Consumer Type
            if mode == "public_transport":
                # User Preferences
                max_wait_time = normal(
                    self._config.user.TRANSIT_MAX_WAIT
                )  # sample from normal dist centered on config

                # Generate Transportation Task
                task = TransportTask(
                    time=self._env.now,
                    origin=origin_position,
                    destination=destination_position,
                    viable_vehicle_types=viable_vehicle_types,
                    max_wait_time=max_wait_time,
                )

                # new_user = user.TransitUser(origin_position, task, self._search_engine, self._payment_engine,
                #                             self._vehicle_assignment_engine, self._vehicle_choice_behavior, self._env,
                #                             passive=True if not self._config.transit_agent_config.dumb else False)
                population_type = None

                new_user = user.TransitUser(
                    sim=self._sim,
                    position=origin_position,
                    transport_task=task,
                    transportation_search_service=self._search_engine[
                        "public_transport_0"
                    ],
                    payment_service=self._payment_engine["public_transport_0"],
                    vehicle_assignment_service=self._vehicle_assignment_engine[
                        "public_transport_0"
                    ],
                    vehicle_choice_behavior=self._vehicle_choice_behavior,
                    population_type=population_type,
                    world=self,
                )
            elif mode == "shared_vehicle":
                # Generate Transportation Task
                task = TransportTask(
                    time=self._env.now,
                    origin=origin_position,
                    destination=destination_position,
                    viable_vehicle_types=viable_vehicle_types,
                )

                # Determine Consumer Type
                population_type = self._population_factory.generatePopulationType()
                # TODO: Remove hard coded operator id
                new_user = user.User(
                    sim=self._sim,
                    fleet=self._operators[fleet].fleet,
                    position=origin_position,
                    transport_task=task,
                    transportation_search_service=self._search_engine[
                        "shared_vehicle_0"
                    ],
                    payment_service=self._payment_engine["shared_vehicle_0"],
                    vehicle_assignment_service=self._vehicle_assignment_engine[
                        "shared_vehicle_0"
                    ],
                    vehicle_choice_behavior=self._vehicle_choice_behavior,
                    population_type=population_type,
                )
                self.logger.debug(
                    " Shared-vehicle user %s starts searching for fleet %s at %s.",
                    new_user.uid,
                    fleet,
                    self._env.now,
                )
            elif mode == "ride_hailing":
                task = TransportTask(
                    self._env.now,
                    origin_position,
                    destination_position,
                    viable_vehicle_types,
                )

                # Determine Consumer Type
                population_type = (
                    self._population_factory.generatePopulationTypeRideHailing()
                )

                new_user = user.RideHailingUser(
                    sim=self._sim,
                    fleet_index=fleet,
                    position=origin_position,
                    transport_task=task,
                    transportation_search_service=self._search_engine[
                        f"ride_hailing_{fleet}"
                    ],
                    payment_service=self._payment_engine[f"ride_hailing_{fleet}"],
                    vehicle_assignment_service=self._vehicle_assignment_engine[
                        f"ride_hailing_{fleet}"
                    ],
                    vehicle_choice_behavior=self._vehicle_choice_behavior,
                    population_type=population_type,
                )
                self.logger.debug(
                    "Ride-hailing user %s, %s request a vehicle at %s.",
                    new_user.uid,
                    population_type,
                    self._env.now,
                )
            elif mode == "walking":
                # Generate Transportation Task
                task = TransportTask(
                    self._env.now,
                    origin_position,
                    destination_position,
                    viable_vehicle_types,
                )

                # Determine Consumer Type
                population_type = self._population_factory.generatePopulationType()

                new_user = user.User(
                    sim=self._sim,
                    fleet=fleet,
                    position=origin_position,
                    transport_task=task,
                    transportation_search_service=self._search_engine["walking"],
                    payment_service=self._payment_engine["walking"],
                    vehicle_assignment_service=self._vehicle_assignment_engine[
                        "walking"
                    ],
                    vehicle_choice_behavior=self._vehicle_choice_behavior,
                    population_type=population_type,
                )
            else:
                raise NotImplementedError('User mode "{mode}" not implemented.')

            # Add user to user set
            self._users.add(new_user)
            # Start Process for each new user
            self._user_processes[new_user.uid] = self._env.process(new_user.run())

            # Spawn cleanup process for that user
            self._env.process(self._cleanup_user(new_user, new_user.uid))

            if len(self._users) == self._user_limit:
                self.logger.info(
                    "Reached User Limit of %s. Not adding more users to world.",
                    self._user_limit,
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

        # Remove user from self._users
        self._users.discard(user)

        # Remove user process from self._user_processes
        if user.uid in self._user_processes:
            del self._user_processes[user.uid]

        self.logger.debug(
            "User %s removed from simulation after process finished.", user.uid
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

    def _load_timetable(self) -> Timetable | None:
        if not hasattr(self._config.path, "PATH_TRANSIT_TIMETABLE"):
            self.logger.warning("No timetable path configured for public transport")
            return None

        from simulation.infrastructure.helper.timetable import Timetable

        timetable_path = os.path.normpath(self._config.path.PATH_TRANSIT_TIMETABLE)
        timetable = Timetable(data_path=timetable_path, sim=self._sim)
        timetable.import_timetable()
        self.logger.info("Loaded public transport timetable from %s", timetable_path)
        return timetable

    def _initialize_public_transport_fleet(self) -> PublicTransportVehicleFleet:
        from simulation.operator.public_transport_vehicle_fleet import (
            PublicTransportVehicleFleet,
        )

        return PublicTransportVehicleFleet(sim=self._sim, world=self)

    def _create_public_transport_search_engine(
        self, operator_config: dict, fleet: PublicTransportVehicleFleet
    ) -> PublicTransportSearchEngine:
        from simulation.operator.public_transport_search_engine import (
            PublicTransportSearchEngine,
        )

        return PublicTransportSearchEngine(
            sim=self._sim, fleet=fleet, operator_config=operator_config
        )

    def _create_public_transport_operations(
        self,
        operator_config: dict,
        timetable: Timetable,
        fleet: PublicTransportVehicleFleet,
    ) -> OperationsPublicTransport:
        from simulation.operator.operations_management.operations_public_transport import (
            OperationsPublicTransport,
        )

        return OperationsPublicTransport(
            sim=self._sim,
            timetable=timetable,
            fleet=fleet,
            operator_config=operator_config,
        )

    def _create_public_transit_operator(
        self,
        fleet: PublicTransportVehicleFleet,
        operations: OperationsPublicTransport,
        search_engine: PublicTransportSearchEngine,
        allocation_engine: PublicTransportAllocationEngine,
    ) -> PublicTransitOperator:
        from simulation.operator.public_transit_operator import PublicTransitOperator

        return PublicTransitOperator(
            sim=self._sim,
            fleet=fleet,
            charging_infrastructure=None,
            operations=operations,
            search_engine=search_engine,
            allocation_engine=allocation_engine,
        )
