"""World: the operators, users, vehicles and charging infrastructures of one simulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.agent.user.user_log import UserLog
from simulation.helper.simulation_base import SimulationBase
from simulation.infrastructure.charging_stations.charging_infrastructure import (
    ChargingInfrastructure,
)
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.operator.operator import Operator, OperatorDependencies
from simulation.world.mobility_search_engine import MobilitySearchEngine

if TYPE_CHECKING:
    import simpy
    from pandas import DataFrame

    from simulation.agent.user.user import User
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_environment import GeodesicEnvironment
    from simulation.helper.configuration.configuration import (
        Configuration,
        OperatorConfig,
    )
    from simulation.helper.random.random_manager import RandomManager
    from simulation.infrastructure.helper.timetable import Timetable
    from simulation.operator.operations_management.operations_public_transport import (
        OperationsPublicTransport,
    )
    from simulation.operator.public_transit_operator import PublicTransitOperator
    from simulation.operator.public_transport_allocation_engine import (
        PublicTransportAllocationEngine,
    )
    from simulation.operator.public_transport_search_engine import (
        PublicTransportSearchEngine,
    )
    from simulation.operator.public_transport_vehicle_fleet import (
        PublicTransportVehicleFleet,
    )
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.vehicle.vehicle import Vehicle


class World(SimulationBase):
    """
    The world.

    The world loads the distance matrix, builds one charging infrastructure per distinct configuration and builds the configured operators.
    The demand factory adds users.
    The vehicle fleets add and remove vehicles.

    Parameters
    ----------
    sim : SimulationContext
        Simulation context with the configuration, geodesic environment and random manager.

    Raises
    ------
    ValueError
        If the configuration defines no operators.
    """

    # There is only one instance of this class.
    __instance = None
    __slots__ = (
        "_changed",
        "_charging_infrastructures",
        "_config",
        "_daily_resolution",
        "_demand_processes",
        "_distance_matrix",
        "_env",
        "_fleets",
        "_geo_env",
        "_market",
        "_mobility_search",
        "_operators",
        "_payment_engine",
        "_random_manager",
        "_search_engine",
        "_sim",
        "_simulation_finished",
        "_spatial_resolution",
        "_temporal_resolution",
        "_total_users",
        "_user_log",
        "_users",
        "_vehicle_assignment_engine",
        "_vehicles",
    )

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._sim: SimulationContext = sim
        self._config: Configuration = sim.config
        self._geo_env: GeodesicEnvironment = sim.geo_env
        self._env: simpy.Environment = sim.env
        self._random_manager = sim.random_manager

        self._distance_matrix: DataFrame = self._load_distance_matrix()

        self._operators: list[Operator] = []

        self._demand_processes: list[simpy.Process] = []

        self._search_engine = {}
        self._payment_engine = {}

        # Store all current users
        self._users: set[User] = set()
        self._total_users: int = 0

        # Store all current vehicles
        # TODO: Probably redundant with fleets
        self._vehicles: set[Vehicle] = set()

        self._fleets: list[VehicleFleet] = []

        self._mobility_search: MobilitySearchEngine = MobilitySearchEngine(
            sim=self._sim
        )

        self._user_log: UserLog = UserLog(sim=self._sim)

        self._charging_infrastructures: list[ChargingInfrastructure] | None = (
            self._initialize_charging_infrastructures()
        )

        self._setup_operators()

        # Events
        self._changed = self._env.event()
        self._simulation_finished = self._env.event()

    @property
    def user_log(self) -> UserLog:
        """User log for system-level trip tracking."""
        return self._user_log

    @property
    def mobility_search(self) -> MobilitySearchEngine:
        """Mobility search engine that users query for transport options."""
        return self._mobility_search

    @property
    def random_manager(self) -> RandomManager:
        """Get the random manager."""
        return self._random_manager

    @property
    def geo_env(self) -> GeodesicEnvironment:
        """Geodesic environment of the simulation."""
        return self._geo_env

    @property
    def distance_matrix(self) -> DataFrame:
        """Get the distance matrix."""
        return self._distance_matrix

    @property
    def demand_processes(self) -> list[simpy.Process]:
        """Demand generation processes, one per spatial unit."""
        return self._demand_processes

    @property
    def operators(self) -> list[Operator]:
        """Get a list of operators in the world."""
        return self._operators

    @property
    def fleets(self) -> list[VehicleFleet]:
        """Get a list of all vehicle fleets in the world."""
        return self._fleets

    def _initialize_charging_infrastructures(
        self,
    ) -> list[ChargingInfrastructure] | None:
        # TODO: This is currently completely ignored by shared vehicle operators, while ridehailing operators all use the same charging infrastructure.
        # This probably needs some refactoring depending on what we want to do with charging infrastructure in the future.
        charging_infrastructures: list[ChargingInfrastructure] = []
        seen: set[int] = set()
        for operator_config in self._config.operators:
            ci_conf = operator_config.CHARGING_INFRASTRUCTURE
            if ci_conf is None or id(ci_conf) in seen:
                continue
            seen.add(id(ci_conf))
            charging_infrastructure = ChargingInfrastructure(
                sim=self._sim, charging_infrastructure_config=ci_conf
            )
            ci_conf.instance = charging_infrastructure
            charging_infrastructures.append(charging_infrastructure)
        return charging_infrastructures or None

    def _setup_operators(self) -> None:
        if not self._config.operators or len(self._config.operators) == 0:
            raise ValueError("No operators defined in configuration.")
        operators = self._config.operators
        for operator_config in operators:
            operator = Operator.from_deps(
                deps=OperatorDependencies(
                    sim=self._sim, config=operator_config, world=self
                )
            )
            self._operators.append(operator)

    def _load_distance_matrix(self) -> DataFrame:
        hexagons = self.geo_env.getLayer("hex").index.tolist()
        dmi = DistanceMatrixImporter(
            hexagons=hexagons,
            resolution=self._config.world.SPATIAL_RESOLUTION,
            cache_dir=self._config.path.cache_dir,
        )
        return dmi.load_distance_matrix()

    def add_user(self, user: User) -> None:
        """Add a user to the world until their process finishes.

        Parameters
        ----------
        user : User
            User to add.
        """
        self._users.add(user)
        self._total_users += 1

        self.logger.debug("User %s added to world.", user.uid)

        user.process_finished.callbacks.append(lambda _event: self._remove_user(user))

    def add_vehicle(self, vehicle: Vehicle) -> None:
        """Add a vehicle to the world."""
        self._vehicles.add(vehicle)

    def remove_vehicle(self, vehicle: Vehicle) -> None:
        """Remove a vehicle from the world, if it is there."""
        self._vehicles.discard(vehicle)

    @property
    def users(self) -> set[User]:
        """Get the set of current users in the world."""
        return self._users

    @property
    def total_users(self) -> int:
        """Get total number of users that have been added to the world so far."""
        return self._total_users

    # TODO: get rid of this, only one user uses it and it should be dealt with differently
    @property
    def vehicles(self) -> set[Vehicle]:
        """Vehicles currently in the world."""
        return self._vehicles

    @property
    def charging_infrastructures(self) -> list[ChargingInfrastructure] | None:
        """Charging infrastructures of the operators, or None if no operator has one."""
        return self._charging_infrastructures

    @property
    def simulation_finished(self) -> simpy.Event:
        """Event that succeeds when the simulation finishes."""
        return self._simulation_finished

    @property
    def changed(self) -> simpy.Event:
        """Event that signals a change of the world."""
        return self._changed

    @changed.setter
    def changed(self, event: simpy.Event) -> None:
        self._changed = event

    def _remove_user(self, user: User) -> None:
        self._users.discard(user)

        self.logger.debug(
            "User %s removed from world after process finished.", user.uid
        )

    def _load_timetable(self) -> Timetable | None:
        timetable_path = self._config.path.transit_timetable
        if timetable_path is None:
            self.logger.warning(
                "No timetable found in DATASET_DIR, skipping public transport"
            )
            return None

        from simulation.infrastructure.helper.timetable import Timetable

        timetable = Timetable(data_path=timetable_path, sim=self._sim)
        timetable.import_timetable()
        self.logger.info("Loaded public transport timetable from %s", timetable_path)
        return timetable

    def _initialize_public_transport_fleet(self) -> PublicTransportVehicleFleet:
        from simulation.operator.public_transport_vehicle_fleet import (
            PublicTransportVehicleFleet,
        )

        # TODO: old, pls fix
        return PublicTransportVehicleFleet(sim=self._sim, world=self)  # pyrefly: ignore[bad-instantiation]

    def _create_public_transport_search_engine(
        self, operator_config: OperatorConfig, fleet: PublicTransportVehicleFleet
    ) -> PublicTransportSearchEngine:
        from simulation.operator.public_transport_search_engine import (
            PublicTransportSearchEngine,
        )

        return PublicTransportSearchEngine(
            sim=self._sim, fleet=fleet, operator_config=operator_config
        )

    def _create_public_transport_operations(
        self,
        operator_config: OperatorConfig,
        timetable: Timetable,
        fleet: PublicTransportVehicleFleet,
    ) -> OperationsPublicTransport:
        from simulation.operator.operations_management.operations_public_transport import (
            OperationsPublicTransport,
        )

        # TODO: old, pls fix
        return OperationsPublicTransport(  # pyrefly: ignore[bad-instantiation]
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
            operations=operations,
            search_engine=search_engine,
            allocation_engine=allocation_engine,
        )
