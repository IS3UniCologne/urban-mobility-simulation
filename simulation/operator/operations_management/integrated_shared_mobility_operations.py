"""Charging and relocation operations for shared mobility operators."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import h3
import pandas as pd

from simulation.helper.enums import VehicleType
from simulation.helper.solvers.tsp_solver_2opt import solve_tsp
from simulation.operator.mixed_shared_vehicle_fleet import MixedSharedVehicleFleet
from simulation.operator.operations_management.operations import (
    Operations,
    OperationsDependencies,
)
from simulation.operator.operations_management.service_jobs.composite_service_job import (
    CompositeServiceJob,
)
from simulation.operator.operations_management.service_jobs.fleet_base_charging_job import (
    FleetBaseChargingJob,
)
from simulation.operator.operations_management.service_jobs.relocation_job import (
    RelocationJob,
)
from simulation.operator.service_workforce import ServiceWorkforce
from simulation.operator.shared_mobility_operator import SharedMobilityOperator

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.helper.types import RegionId
    from simulation.operator.operations_management.service_jobs.service_job import (
        ServiceJob,
    )
    from simulation.operator.operator_log import DemandMonitor
    from simulation.operator.operator_log.demand_monitor import VehicleDemandByRegion

    # (origin, destination, number of vehicles, distance in m)
    PlannedJob = tuple[RegionId, RegionId, float, float]
    # One list of planned jobs per service worker, a list of more than one becomes a composite job
    ServicePlan = dict[VehicleType, list[list[PlannedJob]]]


class IntegratedSharedMobilityOperations(Operations):
    """
    Operations that charge and relocate the vehicles of a shared mobility operator.

    Every ``TIME_BETWEEN_OPERATIONS`` minutes starting at ``OPERATIONS_START``, a cycle of ``OPERATIONS_DURATION`` minutes runs.
    The cycle first schedules charging jobs that bring vehicles below ``RECHARGE_THRESHOLD`` to the fleet base regions.
    Then, until the cycle ends, it repeatedly schedules relocation jobs and waits for them to finish.
    The service workers are split between vehicle types for each plan.

    Parameters
    ----------
    deps : OperationsDependencies
        Construction dependencies.

    Raises
    ------
    TypeError
        If the operations configuration is not an IntegratedSharedMobilityOperationsConfig,
        or the operator's fleet is not a MixedSharedVehicleFleet.
    ValueError
        If the dependencies hold no distance matrix,
        or the configuration has no OPERATIONS_START, OPERATIONS_DURATION or TIME_BETWEEN_OPERATIONS,
        or no single value in RECHARGE_THRESHOLD.
    """

    # TODO: refactor base_regions and capacity, such that it relates to the infrastructure of the operator. This also implies that we need to register the infrastructure after the opeartor is initialised
    __slots__ = (
        "_available_vehicle_types",
        "_base_capacity",
        "_base_regions",
        "_charging_plan_updated",
        "_distances",
        "_duration_of_operations",
        "_geo_env",
        "_max_vehicle_supply",
        "_operations_start",
        "_operations_started",
        "_ordered_max_vehicle_supply",
        "_scheduled_jobs",
        "_sim",
        "_state_of_charge_threshold",
        "_time_between_operations",
        "_workforce",
        "operation_duration",
    )

    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps=deps)

        # configuration imports this module, so a module-level import would be circular
        from simulation.helper.configuration.configuration import (
            IntegratedSharedMobilityOperationsConfig,
        )

        ops_config = deps.operations_config
        if not isinstance(ops_config, IntegratedSharedMobilityOperationsConfig):
            raise TypeError(
                "IntegratedSharedMobilityOperations needs an IntegratedSharedMobilityOperationsConfig."
            )

        self._sim = deps.sim
        self._geo_env = deps.sim.geo_env
        if deps.distance_matrix is None:
            raise ValueError(
                "IntegratedSharedMobilityOperations needs a distance matrix."
            )
        # Distance Matrix between Regions
        self._distances: pd.DataFrame = deps.distance_matrix

        # List needs to be ordered such that:
        # In case of neutral demand, we count the demand for the less expensive option
        # For example: If we observe a demand for KickScooter and Scooter, we count that
        # demand to KickScooter. This ordering is defined according to the following list
        # (from left to right)
        count_by_type = self._fleet.count_by_type
        self._available_vehicle_types: list[VehicleType] = sorted(
            count_by_type.keys(), key=str
        )  # TODO: Remove dependency on ordering
        self._max_vehicle_supply: list[int] = [
            count_by_type[t] for t in self._available_vehicle_types
        ]  # TODO: Remove dependency on ordering

        base_regions = ops_config.BASE_REGIONS
        if ops_config.NUMBER_OF_BASE_REGIONS is not None:
            base_regions = base_regions[: ops_config.NUMBER_OF_BASE_REGIONS]
        self._base_regions: list[RegionId] = base_regions

        self._base_capacity = ops_config.BASE_CAPACITY

        if ops_config.OPERATIONS_START is None:
            raise ValueError(
                "IntegratedSharedMobilityOperations needs OPERATIONS_START."
            )
        self._operations_start: int = ops_config.OPERATIONS_START

        state_of_charge_threshold = ops_config.RECHARGE_THRESHOLD
        if state_of_charge_threshold is None or isinstance(
            state_of_charge_threshold, list
        ):
            raise ValueError(
                "IntegratedSharedMobilityOperations needs RECHARGE_THRESHOLD as a single threshold."
            )
        self._state_of_charge_threshold: float = state_of_charge_threshold

        self._charging_station_power: float = ops_config.CHARGING_STATION_POWER
        self._vehicle_relocation_velocity = ops_config.VEHICLE_RELOCATION_VELOCITY

        # TODO: move to workforce? or internal schedule?
        self._scheduled_jobs: list[ServiceJob] = []

        # Events
        self._charging_plan_updated: Event = self._env.event()
        self._operations_started: Event = self._env.event()

        # When to start operations (every 1440 min)
        if ops_config.TIME_BETWEEN_OPERATIONS is None:
            raise ValueError(
                "IntegratedSharedMobilityOperations needs TIME_BETWEEN_OPERATIONS."
            )
        self._time_between_operations: int = ops_config.TIME_BETWEEN_OPERATIONS

        # Shift Duration (OM shift duration)
        if ops_config.OPERATIONS_DURATION is None:
            raise ValueError(
                "IntegratedSharedMobilityOperations needs OPERATIONS_DURATION."
            )
        self._duration_of_operations: int = ops_config.OPERATIONS_DURATION  # mins

        # Shared Mobility specific: Service Workforce
        self._workforce = ServiceWorkforce(
            sim=self._sim,
            number_service_workers=ops_config.NUMBER_OF_SERVICE_WORKERS,
            cost_config=ops_config.WORKER_COST_CONFIG,
            ledger=self.operator.ledger,
        )

    @property
    def available_vehicle_types(self) -> list[VehicleType]:
        """Vehicle types of the fleet, in the order every plan and capacity split uses."""
        return self._available_vehicle_types

    @property
    def _fleet(self) -> MixedSharedVehicleFleet:
        fleet = self._operator.fleet
        if not isinstance(fleet, MixedSharedVehicleFleet):
            raise TypeError(
                "IntegratedSharedMobilityOperations needs a MixedSharedVehicleFleet."
            )
        return fleet

    @property
    def _demand_monitor(self) -> DemandMonitor:
        operator = self._operator
        if not isinstance(operator, SharedMobilityOperator):
            raise TypeError(
                "IntegratedSharedMobilityOperations needs a SharedMobilityOperator."
            )
        return operator.demand_monitor

    def execute(self) -> Generator[Event, Any, None]:
        """Run the operations cycles: charging first, then relocation until the cycle ends.

        Yields
        ------
        Event
            Timeout until the next step, or the condition that the scheduled jobs finished.

        Raises
        ------
        TypeError
            If the operator is not a SharedMobilityOperator.
        """
        # Wait for operations to start
        if self._operations_start > 0:
            yield self._env.timeout(self._operations_start)

        while True:
            cycle_start = self._env.now
            cycle_end = cycle_start + self._duration_of_operations

            # Clean old jobs (if there are some left)
            self._scheduled_jobs.clear()
            self._workforce.job_queue.clear()

            if not self.operator.operator_log.has_successful_transaction:
                self.logger.debug(
                    "No successful transactions yet, skipping operations cycle."
                )
                yield self._env.timeout(self._time_between_operations)
                continue

            # Retrieve Charging Plan to Charge Vehicles with low State of Charge
            charging_plans = self.generate_charging_plan()

            # We track the charging events
            charging_events: list[Event] = []

            # No Vehicles to be charged
            no_vehicles_scheduled_to_charge: dict[VehicleType, float] = {}

            for type in self._available_vehicle_types:
                charging_plans_for_current_type = charging_plans[type]

                # Set Counter to 0
                if type not in no_vehicles_scheduled_to_charge:
                    no_vehicles_scheduled_to_charge[type] = 0

                for charging_plan in charging_plans_for_current_type:
                    if len(charging_plan) > 1:
                        composite_job = CompositeServiceJob(self._sim)
                        # Pooled Task
                        for entry in charging_plan:
                            (
                                origin,
                                destination,
                                no_vehicle_to_charge,
                                distance_to_base,
                            ) = entry

                            charging_job = FleetBaseChargingJob(
                                sim=self._sim,
                                origin=origin,
                                destination=destination,
                                number_of_vehicles_to_charge=int(no_vehicle_to_charge),
                                vehicle_type=type,
                                distance_to_fleet_base=distance_to_base,
                                vehicle_fleet=self._fleet,
                                state_of_charge_threshold=self._state_of_charge_threshold,
                                charging_power=self._charging_station_power,
                                vehicle_relocation_velocity=self._vehicle_relocation_velocity,
                            )

                            composite_job.append_job(charging_job)

                            # Count Vehicles to be charged
                            no_vehicles_scheduled_to_charge[type] += (
                                no_vehicle_to_charge
                            )

                        # Schedule to Queue
                        self._scheduled_jobs.append(composite_job)

                        # Remember event for multi service tasks
                        charging_events.append(composite_job.finished)
                    else:
                        # Single Task
                        origin, destination, no_vehicle_to_charge, distance_to_base = (
                            charging_plan[0]
                        )

                        charging_job = FleetBaseChargingJob(
                            sim=self._sim,
                            origin=origin,
                            destination=destination,
                            number_of_vehicles_to_charge=int(no_vehicle_to_charge),
                            vehicle_type=type,
                            distance_to_fleet_base=distance_to_base,
                            vehicle_fleet=self._fleet,
                            state_of_charge_threshold=self._state_of_charge_threshold,
                            charging_power=self._charging_station_power,
                            vehicle_relocation_velocity=self._vehicle_relocation_velocity,
                        )

                        # Schedule to Queue
                        self._scheduled_jobs.append(charging_job)

                        # Remember event for multi service tasks
                        charging_events.append(charging_job.finished)

                        # Count Vehicles to be charged
                        no_vehicles_scheduled_to_charge[type] += no_vehicle_to_charge

            # Insert Tasks into Task Queue
            self._workforce.job_queue.bulk_append(self._scheduled_jobs)

            self.logger.info(
                "There are %s vehicles with low state of charge.",
                len(
                    self._fleet.vehicles_below_energy_threshold(
                        self._state_of_charge_threshold
                    )
                ),
            )

            self.logger.info(
                "Charging jobs scheduled. In total %s generated. Count: %s",
                len(charging_events),
                no_vehicles_scheduled_to_charge,
            )

            # Notify listeners
            self._charging_plan_updated.succeed()
            self._charging_plan_updated = self._env.event()

            # Relocation phase (while within operations window)
            while self._env.now < cycle_end:
                self.logger.info("Planning next relocation schedule.")

                # Reset Scheduled Tasks
                self._scheduled_jobs.clear()

                # Wait 2 Minutes, then (re-)schedule relocation
                yield self._env.timeout(2)

                relocations = self.generate_relocation_plan()

                # We track the charging events
                relocation_events: list[Event] = []

                # No Vehicles to be charged
                no_vehicles_scheduled_to_relocate: dict[VehicleType, float] = {}

                for type in self._available_vehicle_types:
                    relocation_plans_for_current_type = relocations[type]

                    # Set Counter to 0
                    if type not in no_vehicles_scheduled_to_relocate:
                        no_vehicles_scheduled_to_relocate[type] = 0

                    for relocation_plan in relocation_plans_for_current_type:
                        if len(relocation_plan) > 1:
                            composite_job = CompositeServiceJob(self._sim)
                            # Pooled Task
                            for entry in relocation_plan:
                                (
                                    origin,
                                    destination,
                                    no_vehicle_to_relocate,
                                    relocation_distance,
                                ) = entry

                                relocation_job = RelocationJob(
                                    sim=self._sim,
                                    origin=origin,
                                    destination=destination,
                                    number_of_vehicles_to_relocate=int(
                                        no_vehicle_to_relocate
                                    ),
                                    distance=relocation_distance,
                                    vehicle_type=type,
                                    vehicle_fleet=self._fleet,
                                    vehicle_relocation_velocity_mm=self._vehicle_relocation_velocity,
                                )

                                composite_job.append_job(relocation_job)

                                # Count Vehicles to be charged
                                no_vehicles_scheduled_to_relocate[type] += (
                                    no_vehicle_to_relocate
                                )

                            # Schedule to Queue
                            self._scheduled_jobs.append(composite_job)

                            # Remember event for multi service tasks
                            relocation_events.append(composite_job.finished)
                        else:
                            # Single Task
                            (
                                origin,
                                destination,
                                no_vehicle_to_relocate,
                                relocation_distance,
                            ) = relocation_plan[0]

                            relocation_job = RelocationJob(
                                sim=self._sim,
                                origin=origin,
                                destination=destination,
                                number_of_vehicles_to_relocate=int(
                                    no_vehicle_to_relocate
                                ),
                                distance=relocation_distance,
                                vehicle_type=type,
                                vehicle_fleet=self._fleet,
                                vehicle_relocation_velocity_mm=self._vehicle_relocation_velocity,
                            )

                            # Schedule to Queue
                            self._scheduled_jobs.append(relocation_job)

                            # Remember event for multi service tasks
                            relocation_events.append(relocation_job.finished)

                            # Count Vehicles to be charged
                            no_vehicles_scheduled_to_relocate[type] += (
                                no_vehicle_to_relocate
                            )

                # Insert Tasks into Task Queue
                self._workforce.job_queue.bulk_append(self._scheduled_jobs)

                if len(charging_events):
                    # Wait for Charging events
                    yield self._env.all_of(charging_events)

                    self.logger.info(
                        "All charging jobs have been fulfilled. Re-generating relocation plan."
                    )

                # Wait for relocation events to be processed
                yield self._env.all_of(relocation_events)

                self.logger.info(
                    "All relocation jobs have been fulfilled. Re-generating relocation plan."
                )

            # Wait until next cycle
            next_cycle = cycle_start + self._time_between_operations
            wait_time = max(0, next_cycle - self._env.now)
            yield self._env.timeout(wait_time)

    def generate_relocation_plan(self) -> ServicePlan:
        """Plan relocations from the current fleet state and the observed demand.

        Returns
        -------
        dict of VehicleType to list of list of tuple
            Relocation plan, as identify_potential_relocations returns it.

        Raises
        ------
        TypeError
            If the operator is not a SharedMobilityOperator.
        """
        fleet_state = self.calculate_residual_supply(self._fleet, self._demand_monitor)

        relocation_plans = self.identify_potential_relocations(fleet_state)

        return relocation_plans

    def generate_charging_plan(self) -> ServicePlan:
        """Generate a rule based charging plan based on given service worker capacity.

        Writes the fleet state to FLEET_STATE_FILE when PERSIST_RESULTS is set.

        Returns
        -------
        dict of VehicleType to list of list of tuple
            Charging plan, as calculate_charging_plan returns it.

        Raises
        ------
        TypeError
            If the operator is not a SharedMobilityOperator.
        """
        # Get Current Fleet State
        state = self.calculate_residual_supply(self._fleet, self._demand_monitor)

        # TODO :remove this? The whole persist results setting should be looked into
        if self._sim.config.settings.PERSIST_RESULTS:
            state.to_csv(
                Path(
                    self._sim.config.path.OUTPUT_FOLDER,
                    self._sim.config.path.FLEET_STATE_FILE,
                ),
                index=False,
            )

        charging_plans = self.calculate_charging_plan(state)

        return charging_plans

    #############################################
    #############################################
    #  Charging Planing                         #
    #############################################
    #############################################

    def calculate_charging_plan(self, fleet_state: pd.DataFrame) -> ServicePlan:
        """Plan which service worker brings which low state of charge vehicles to a fleet base region.

        For each vehicle type, regions with the most low state of charge vehicles come first.
        One service worker picks up at most get_max_capacity_per_unit vehicles.
        When a region has fewer, the same worker also collects from the neighbour regions.
        The number of service workers per vehicle type comes from calculate_resource_capacity_split_for_charging.

        Parameters
        ----------
        fleet_state : pandas.DataFrame
            Fleet state, as calculate_residual_supply returns it.

        Returns
        -------
        dict of VehicleType to list of list of tuple
            Charging jobs per vehicle type, one inner list per service worker.
            Each tuple is (origin, fleet base region, number of vehicles, distance in m).
            The first tuple of a list holds the distance to the fleet base region,
            the other tuples the distance from their neighbour region to the first region.
        """
        # Fleet State
        state = fleet_state

        # How much capacity is already "used"
        # free_base_capacity = dict(
        #     zip(self._base_regions, [self._base_capacity] * len(self._base_regions))
        # )

        # Split available service worker resources among vehicle types
        # (prioritize vehicles where most low soc vehicles are present)
        capacity_per_type = self.calculate_resource_capacity_split_for_charging(
            state, self._max_vehicle_supply, self._workforce.number_service_workers
        )

        # We calculate for each vehicle mode dedicated charging plans based on the available resources
        all_charging_plans: ServicePlan = {}

        for i, type in enumerate(self._available_vehicle_types):
            # Sort State by Regions with highest number of SoC (per vehicle)
            state = state.sort_values(
                by=[f"{type}_Low_SoC", "hex_id"], ascending=[False, True]
            )

            # Get Max Charging Capacity per Service Worker Unit
            # e.g., 40 Kick Scooters by one SW, 1 Car by one SW
            max_capacity_per_unit = self.get_max_capacity_per_unit(type)

            # Mode Specific Service Unit Resources (i.e., how many service workers have we assigned to collect the current mode)
            number_service_workers_per_type = capacity_per_type[i]

            # Keep track of vehicles which are already scheduled for pick up and charging per region
            already_scheduled_low_vehicles: dict[RegionId, float] = {}

            # Resulting charging plan having charging tasks per service worker
            # Each element represents one pick up and charging task
            # each element can consist of multiple tasks since vehicles from nearby regions can also be collected if
            # space if available.
            # Example [(origin, destination, number of vehicles to pick up, destination to base)]
            # Multitask Example
            # [
            #  ('871f1d49dffffff', '871f1d488ffffff', 24.0, 4173.489610482256),
            #  ('871f1d48effffff', '871f1d488ffffff', 16.0, 2312.641785385671) <- This is the neighbour of 871f1d49dffffff, distance to neighbour
            # ]
            # Note that the first element has the distance to the base and all other elements are relative to the first (main) region.
            charging_plan: list[list[PlannedJob]] = []

            for index, row in state.iterrows():
                next_hex_id = row["hex_id"]

                # Break loop if service worker resources are depleted
                if len(charging_plan) == number_service_workers_per_type:
                    # No more service worker capacity, stop planning
                    break

                # Get nearest fleet base region (.loc -> destination, [[]] -> Origin)
                sorted_base_list = self._distances.loc[self._base_regions][
                    [next_hex_id]
                ].sort_values(by=next_hex_id, ascending=True)

                # How many vehicles are already schedules for pick up?
                if next_hex_id not in already_scheduled_low_vehicles:
                    already_scheduled_low_vehicles[next_hex_id] = 0

                # TODO: we take the last row, the farthest base, not the nearest.
                selected_base = sorted_base_list.index[-1]
                selected_base_distance = sorted_base_list[next_hex_id].iloc[-1]

                while (
                    len(charging_plan) != number_service_workers_per_type
                    and already_scheduled_low_vehicles[next_hex_id]
                    != row[f"{type}_Low_SoC"]
                ):
                    # Keep Track of how many vehicles are already scheduled for charging
                    currently_schedules_vehicles_per_unit = 0

                    # How many vehicles can we move to the base and charge?
                    pick_up_vehicles = min(
                        (
                            row[f"{type}_Low_SoC"]
                            - already_scheduled_low_vehicles[next_hex_id]
                        ),
                        max_capacity_per_unit,
                    )

                    # currently_schedules_vehicles_per_unit
                    currently_schedules_vehicles_per_unit += pick_up_vehicles

                    # Update Already Picked Up Vehicle Dict
                    already_scheduled_low_vehicles[next_hex_id] += pick_up_vehicles

                    # Collection of Charging Tasks per Service Worker
                    chargings_tasks: list[PlannedJob] = []

                    # Charging Task from current region to fleet base
                    charging_task = (
                        next_hex_id,
                        selected_base,
                        pick_up_vehicles,
                        selected_base_distance,
                    )

                    # Add main chargin task to charging tasks
                    if pick_up_vehicles > 0:
                        chargings_tasks.append(charging_task)

                    # If we still have capacity, and no more vehicles are in the region
                    if (
                        pick_up_vehicles < max_capacity_per_unit
                        and pick_up_vehicles > 0
                    ):
                        neighbours = h3.grid_disk(next_hex_id, 1)
                        neighbours.remove(
                            next_hex_id
                        )  # Consider only neighbours (not current region)

                        # Consider only Fleet State of neighbour regions
                        neighbour_states = state[state["hex_id"].isin(neighbours)]
                        # TODO: is this necessary ?
                        neighbour_states = neighbour_states.sort_values(by="hex_id")

                        for index_adjacent, row_adjacent in neighbour_states.iterrows():
                            adjacent_hex_id = row_adjacent["hex_id"]

                            # How many vehicles from the adjacent regions are already schedules for pick up?
                            if adjacent_hex_id not in already_scheduled_low_vehicles:
                                already_scheduled_low_vehicles[adjacent_hex_id] = 0

                            # How many vehicles can we move from the adjacent hex to the base and charge them?
                            pick_up_vehicles_from_adjacent_region = min(
                                (
                                    row_adjacent[f"{type}_Low_SoC"]
                                    - already_scheduled_low_vehicles[adjacent_hex_id]
                                ),
                                max_capacity_per_unit
                                - currently_schedules_vehicles_per_unit,
                            )

                            # Can we pick up any vehicles from that neighbour? If yes, append charging task
                            if pick_up_vehicles_from_adjacent_region > 0:
                                # currently_schedules_vehicles_per_unit
                                currently_schedules_vehicles_per_unit += (
                                    pick_up_vehicles_from_adjacent_region
                                )

                                # Update Already Picked Up Vehicle Dict
                                already_scheduled_low_vehicles[adjacent_hex_id] += (
                                    pick_up_vehicles_from_adjacent_region
                                )

                                # Distance to Neighbour
                                distance_to_neighbour = self._distances.loc[
                                    adjacent_hex_id
                                ][next_hex_id]

                                # add additional charging task
                                charging_task = (
                                    adjacent_hex_id,
                                    selected_base,
                                    pick_up_vehicles_from_adjacent_region,
                                    distance_to_neighbour,
                                )

                                # Add to Charging Tasks list (i.e., this is a multitask object; one service workers needs to visit multiple regions)
                                chargings_tasks.append(charging_task)

                    # Store Charging Task
                    if len(chargings_tasks) > 0:
                        charging_plan.append(chargings_tasks)

            # Save Charging Plan of Vehicle Mode
            all_charging_plans[type] = charging_plan

        # Count planned resources (e.g., service workers needed to execute planned charging jobs)
        used_resources = 0
        for key in all_charging_plans:
            used_resources += len(all_charging_plans[key])

        return all_charging_plans

    def calculate_resource_capacity_split_for_charging(
        self,
        fleet_state: pd.DataFrame,
        max_vehicle_supply: list[int],
        number_service_workers_per_mode: int,
    ) -> list[int]:
        """Split the service workers between vehicle types for charging.

        Each vehicle type gets a share in proportion to its weight,
        low state of charge vehicles / get_max_capacity_per_unit / fleet size of the type.
        Dividing by get_max_capacity_per_unit keeps types that one worker collects in bulk,
        such as kick scooters, from taking most of the workers.
        Rounding residue goes to the type with the most workers.

        Parameters
        ----------
        fleet_state : pandas.DataFrame
            Fleet state, as calculate_residual_supply returns it.
        max_vehicle_supply : list of int
            Fleet size per vehicle type, in the order of available_vehicle_types.
        number_service_workers_per_mode : int
            Total number of service workers to split.

        Returns
        -------
        list of int
            Number of service workers per vehicle type, in the order of available_vehicle_types.
            All zero when no vehicle needs charging.
        """
        current_low_soc_supply: list[float] = []

        for mode in self._available_vehicle_types:
            # Service Worker Charging Capacity per Mode
            max_capacity_per_unit = self.get_max_capacity_per_unit(mode)

            # Normalize the vehicle weight;
            # otherwise all resources are bound to kick scooters as there are way more low soc kick scooters
            # One Service Worker can "process" 40 units of kick scooters compared to 1 sw for one car.
            current_low_soc_supply.append(
                fleet_state[f"{mode}_Low_SoC"].sum() / max_capacity_per_unit
            )

        low_fraction_per_mode = [
            curr_low_supply / max_supply if max_supply != 0 else 0
            for curr_low_supply, max_supply in zip(
                current_low_soc_supply, max_vehicle_supply
            )
        ]

        # Temporary Denom
        denominator = sum(low_fraction_per_mode)

        if denominator == 0.0:
            # No Charging Needed => No Workers assigned
            return len(low_fraction_per_mode) * [0]

        # Split capacity based on the following fraction
        capacity = [
            round(fraction / denominator * number_service_workers_per_mode)
            for fraction in low_fraction_per_mode
        ]

        # Rounding Fractions => Sum of Residual don't add up to available units
        # We fix this by adding or subtracting the residual to the max. element
        # Happens very rarely
        residual = number_service_workers_per_mode - sum(capacity)

        max_element = max(capacity)
        arg_max = capacity.index(max_element)

        if residual > 0:
            # We add excess supply to mode where most workforce is needed
            capacity[arg_max] += residual
        elif residual < 0:
            capacity[arg_max] = max(capacity[arg_max] + residual, 0)

        return capacity

    # TODO: This should not be hardcoded
    def get_max_capacity_per_unit(self, vehicle_type: VehicleType) -> int:
        """Return how many vehicles of a type one service worker collects in one job.

        Parameters
        ----------
        vehicle_type : VehicleType
            Vehicle type to look up.

        Returns
        -------
        int
            40 for kick scooters, 8 for bikes and scooters, 1 for cars.

        Raises
        ------
        NotImplementedError
            If the vehicle type has no capacity.
        """
        # Mode Specific Collection Capacity per Service Worker (i.e., how many vehicles can one sw collect)
        if vehicle_type == VehicleType.KICK_SCOOTER:
            max_capacity_per_unit = 40
        elif vehicle_type == VehicleType.BIKE:
            max_capacity_per_unit = 8
        elif vehicle_type == VehicleType.SCOOTER:
            max_capacity_per_unit = 8
        elif vehicle_type == VehicleType.CAR:
            max_capacity_per_unit = 1
        else:
            raise NotImplementedError(
                f"No service worker capacity for vehicle type {vehicle_type}."
            )
        return max_capacity_per_unit

    #############################################
    #############################################
    #  Relocation Planing                       #
    #############################################
    #############################################

    def identify_potential_relocations(self, state: pd.DataFrame) -> ServicePlan:
        """Plan relocations from regions with excess supply to regions with a supply shortfall.

        Calculate how many vehicles need to be moved (or can be) from origin to destination

          Approach:Calculate state of the fleet. Relocate vehicles from regions with positive residual (excess of vehicles)
          to regions with negative residuals (lack of vehicles). We differentiate between two types of relocations.

          Single Vehicle and Pooled Relocations. Cars for example are single relocation, kick scooters are relocated in a pooled fashion.

          The single relocation case is simple. Relocate vehicles from nearest regions with excess vehicle supply.

          The pooled relocation process is more complicated. First, we identify the target region with lack of
          vehicle supply. Typically, we begin with the region with vehicle lack. We then find regions nearby
          where vehicles are abundant. Then, we try to relocate as much vehicles from that region to the target region.
          In general, we try to avoid pooling vehicles from multiple region (i.e., deplete supply in a region).

          However, if there is space left for other vehicles within the relocation pool, we spot the next region
          where vehicles are available. We continue until the pooling capacity is reached. After having identified
          the candidate regions along with the vehicles to be relocated, we calculate the shortest pick up route
          by solving the traveling salesman problem.

        Parameters
        ----------
        state : pandas.DataFrame
            Fleet state, as calculate_residual_supply returns it.

        Returns
        -------
        dict of VehicleType to list of list of tuple
            Relocation jobs per vehicle type, one inner list per service worker.
            Each tuple is (origin, destination, number of vehicles, distance in m).
        """
        # TODO: sanity check if vehicles that are in regions without demand (neither origin nor destination) are abandoned or will be relocated to promised land
        relocations: ServicePlan = {}

        # Split available service worker resources among vehicle types
        # (prioritize vehicles where most low soc vehicles are present)
        capacity_per_mode = self.calculate_resource_capacity_split_for_relocation(
            state, self._max_vehicle_supply, self._workforce.number_service_workers
        )
        for i, mode in enumerate(self._available_vehicle_types):
            # Relocation List containing tuples (origin, destination, number_of_vehicles_to_be_relocated, distance)
            relocation_list: list[list[PlannedJob]] = []

            relocations[mode] = relocation_list

            # Get Max Charging Capacity per Service Worker Unit
            # e.g., 40 Kick Scooters by one SW, 1 Car by one SW
            max_capacity_per_unit = self.get_max_capacity_per_unit(mode)

            # Mode Specific Service Unit Resources (i.e., how many service workers have we assigned to collect the current mode)
            number_service_workers_per_mode = capacity_per_mode[i]

            # Already Relocated Vehicles
            hexagons = sorted(state["hex_id"].unique())
            already_relocated = dict(zip(hexagons, [0] * len(hexagons)))

            # Sort Ascending
            state = state.sort_values(by=[f"Residual_Supply_{mode}", "hex_id"])

            for index, next_hex in state[
                state[f"Residual_Supply_{mode}"] < 0
            ].iterrows():
                """
                  Iterate through each hexagon where we expect a negative supply (i.e., demand and supply don't match)
                  Start with hexagon with highest lack of vehicle supply
                """
                next_hex_id = next_hex["hex_id"]
                residual_supply = next_hex[f"Residual_Supply_{mode}"]

                # Already Relocated Vehicles into this Hexagon
                relocated_vehicles = 0

                # Break loop if service worker resources are depleted
                if len(relocation_list) == number_service_workers_per_mode:
                    # No more service worker capacity, stop planning
                    break

                # Get Distance To All Other Regions
                sub_distance_matrix = self._distances[[next_hex_id]].reset_index()
                sub_distance_matrix = sub_distance_matrix.rename(
                    columns={"index": "hex_id"}
                )

                # Merge Sub Distance Matrix of selected Region with Relocation Plan
                # We obtain for the current hexagon a list of all hexagons along with their current vehicle supply
                distance_to_other_hexagons = sub_distance_matrix.merge(
                    state, how="inner", on="hex_id"
                )

                # Sort by distance (in meter) (i.e., prefer neighbours first)
                distance_to_other_hexagons = distance_to_other_hexagons.sort_values(
                    by=[next_hex_id, "hex_id"]
                )

                # Only consider regions having additional supply
                distance_to_other_hexagons = distance_to_other_hexagons[
                    distance_to_other_hexagons[f"Residual_Supply_{mode}"] > 0
                ]
                distance_to_other_hexagons[f"Relocate_{mode}"] = 0

                # Calculate for the current hexagon the number of vehicles to be relocated from other regions.
                idx = []
                local_relocation_schedule = []

                for index, row in distance_to_other_hexagons.iterrows():
                    # Minimum between available vehicles (i.e., only relocate vehicles which are there, now!)
                    vehicle_buffer = 3
                    # -3 is our buffer
                    physicially_available_vehicles = min(
                        row[f"Residual_Supply_{mode}"],
                        max(row[f"{mode}"] - vehicle_buffer, 0),
                    )

                    if physicially_available_vehicles <= 0:
                        continue  # We cannot use this region to get vehicles

                    # Relocatable Vehicles = Additional Vehicles - Already (Planned) for Relocation Vehicles
                    relocatable_vehicles = (
                        physicially_available_vehicles
                        - already_relocated[row["hex_id"]]
                    )
                    # We relocate only either the availalbe number of relocatable vehicles or missing number of vehicles
                    relocate = min(
                        relocatable_vehicles, abs(residual_supply) - relocated_vehicles
                    )

                    # Increment relocated vehicles counter
                    relocated_vehicles += relocate

                    # How many vehicles are still left in that hexagon
                    # Important for the determination of vehicle relocations for remaining regions
                    already_relocated[row["hex_id"]] += relocate

                    # We use lists here and append them later to the DataFrame
                    idx.append(index)
                    local_relocation_schedule.append(relocate)

                # Break loop if there is no "excess" supply
                if len(local_relocation_schedule) == 0:
                    self.logger.info(
                        "Cannot calculate relocation plan for %s as there are no regions with excess supply.",
                        mode,
                    )
                    break

                # Append No. of Vehicles to be relocated
                distance_to_other_hexagons[f"Relocate_{mode}"] = pd.DataFrame(
                    local_relocation_schedule, index=idx
                )

                # Pool Relocations and split tasks by capacity of each service worker.
                tmp_list: list[PlannedJob] = []
                tmp_counter = 0
                for _, row in distance_to_other_hexagons[
                    distance_to_other_hexagons[f"Relocate_{mode}"] > 0
                ].iterrows():
                    vehicles_to_relocate = row[f"Relocate_{mode}"]
                    # First create relocation jobs that can immediately provide vehicles without "visiting" nearby areas
                    while (
                        vehicles_to_relocate >= max_capacity_per_unit
                        and len(relocation_list) < number_service_workers_per_mode
                    ):
                        relocation_list.append(
                            [
                                (
                                    row["hex_id"],
                                    next_hex_id,
                                    max_capacity_per_unit,
                                    row[next_hex_id],
                                )
                            ]
                        )
                        vehicles_to_relocate -= max_capacity_per_unit

                    if len(relocation_list) == number_service_workers_per_mode:
                        # No more service worker capacity, stop planning
                        break

                    # Remaining capacity of service worker
                    local_missing_supply = max_capacity_per_unit - tmp_counter

                    local_relocatable_vehicles = min(
                        vehicles_to_relocate, local_missing_supply
                    )

                    # Pool Relocation Tasks as worker has still some capacity
                    if (
                        tmp_counter + local_relocatable_vehicles
                        <= max_capacity_per_unit
                        and local_relocatable_vehicles > 0
                    ):
                        tmp_list.append(
                            (
                                row["hex_id"],
                                next_hex_id,
                                local_relocatable_vehicles,
                                row[next_hex_id],
                            )
                        )
                        tmp_counter += local_relocatable_vehicles

                        # TODO: once a pool is full, the rest of that region and all of the next region are never planned: should we carry them into the next pool?
                    else:
                        # Start new pooled task as capacity is depleted of current service worker.
                        # List of (Origin, Destination, No. Vehicles to Relocate, Distance from Origin to Distance)
                        if len(tmp_list) > 0:
                            relocation_list.append(tmp_list)

                        # Reset
                        tmp_list = []
                        tmp_counter = 0

                if (
                    len(relocation_list) < number_service_workers_per_mode
                    and len(tmp_list) > 0
                ):
                    relocation_list.append(tmp_list)

            # If multiple hexagons are visited to pick up vehicles, we need to solve the traveling salesman problem
            for relocation in relocation_list:
                if len(relocation) > 1:
                    hexagons = {}

                    for tuple_idx, tuple in enumerate(relocation):
                        origin, destination, _, _ = tuple

                        # We relocate vehicles to this position => Index 0
                        if tuple_idx == 0:
                            hexagons[destination] = tuple_idx

                        # From here
                        hexagons[origin] = tuple_idx + 1

                    tsp_result = solve_tsp(hexagons, self._distances)
                    tour_sequence, tour_length, dist_lookup = (
                        tsp_result.tour_sequence,
                        tsp_result.tour_length,
                        tsp_result.distance_lookup,
                    )

                    # Find the predecessor and successor of destination in the tour
                    index_of_destination = tour_sequence.index(0)
                    predecessor_idx = (index_of_destination - 1) % len(tour_sequence)
                    successor_idx = (index_of_destination + 1) % len(tour_sequence)

                    # Compare costs of the two possible edges to remove
                    # TODO: both lookups miss the tuple keys of dist_lookup and return their second argument, a node index: should we read dist_lookup[(a, b)]?
                    cost_entering_dest = dist_lookup.get(  # pyrefly: ignore[no-matching-overload]
                        tour_sequence[predecessor_idx],
                        tour_sequence[index_of_destination],
                    )

                    cost_exiting_dest = dist_lookup.get(  # pyrefly: ignore[no-matching-overload]
                        tour_sequence[index_of_destination],
                        tour_sequence[successor_idx],
                    )

                    if cost_entering_dest > cost_exiting_dest:
                        # Remove edge entering destination by placing destination at the start
                        tour_sequence = (
                            tour_sequence[index_of_destination:]
                            + tour_sequence[:index_of_destination]
                        )
                        excess_distance = cost_entering_dest
                    else:
                        # Remove edge exiting destination by placing destination at the end
                        tour_sequence = (
                            tour_sequence[(index_of_destination + 1) :]
                            + tour_sequence[: (index_of_destination + 1)]
                        )
                        excess_distance = cost_exiting_dest

                    # Remove the distance from the "destination" to the "origin" of the relocation trip
                    total_distance = tour_length - excess_distance

                    average_distance_per_relocation_step = total_distance / len(
                        relocation
                    )

                    # Override distances based on calculated traveling salesman problem solution
                    relocation[:] = [
                        (
                            origin,
                            destination,
                            number_of_vehicles,
                            average_distance_per_relocation_step,
                        )
                        for origin, destination, number_of_vehicles, _ in relocation
                    ]

        return relocations

    def calculate_resource_capacity_split_for_relocation(
        self,
        fleet_state: pd.DataFrame,
        max_vehicle_supply: list[int],
        number_service_workers_per_mode: int,
    ) -> list[int]:
        """Determine Service Worker Split Between Modes.

        Each vehicle type gets a share in proportion to its weight,
        sum of absolute residual supply / get_max_capacity_per_unit / fleet size of the type.
        No type gets more workers than it needs to move its whole fleet once.
        Workers left over from rounding go to the types below that limit, one at a time.

        Parameters
        ----------
        fleet_state : pandas.DataFrame
            Fleet state, as calculate_residual_supply returns it.
        max_vehicle_supply : list of int
            Fleet size per vehicle type, in the order of available_vehicle_types.
        number_service_workers_per_mode : int
            Total number of service workers to split.

        Returns
        -------
        list of int
            Number of service workers per vehicle type, in the order of available_vehicle_types.
            All zero when supply matches demand in every region.
        """
        current_supply_mismatch: list[float] = []

        max_unit_assignment: list[int] = []

        for idx, mode in enumerate(self._available_vehicle_types):
            # Service Worker Relocation Capacity per Mode
            max_capacity_per_unit = self.get_max_capacity_per_unit(mode)

            # Normalize the vehicle weight;
            # One Service Worker can "process" 40 units of kick scooters compared to 1 sw for one car.
            current_supply_mismatch.append(
                fleet_state[f"Residual_Supply_{mode}"].abs().sum()
                / max_capacity_per_unit
            )

            max_unit_assignment.append(
                round(max_vehicle_supply[idx] / max_capacity_per_unit + 0.49)
            )  # Round Up

        # Normalize by number of vehicles
        current_supply_mismatch = [
            supply_mismatch / max_supply if max_supply != 0 else 0
            for supply_mismatch, max_supply in zip(
                current_supply_mismatch, max_vehicle_supply
            )
        ]

        # Temporary Denom
        denominator = sum(current_supply_mismatch)

        if denominator == 0.0:
            # No Relocations Needed => No Workers assigned
            return len(current_supply_mismatch) * [0]

        # Split capacity based on the following fraction
        capacity = [
            round(mismatch / denominator * number_service_workers_per_mode)
            for mismatch in current_supply_mismatch
        ]

        capacity = [
            min(capa, max_unit_assign)
            for capa, max_unit_assign in zip(capacity, max_unit_assignment)
        ]

        # Rounding Fractions => Sum of Residual don't add up to available units
        # We fix this by adding or subtracting the residual to the max. element
        # Happens very rarely
        residual = number_service_workers_per_mode - sum(capacity)

        # Residual ensures that we deplete all available service workers
        # the second condition ensures that we only do this until we have reached "needed" capacity to do operations.
        # For example: If we have very low number of vehicles, but a high number of service workers,
        #              we will have a lot residuals but we don't need them as capacity is already equal max_unit_assignment.
        while residual > 0 and sum(capacity) < sum(max_unit_assignment):
            for idx, elem in enumerate(capacity):
                if residual > 0:
                    if capacity[idx] < max_unit_assignment[idx]:
                        capacity[idx] += 1
                        residual -= 1
        return capacity

    #############################################
    #############################################
    #  Fleet State Analysis                     #
    #############################################
    #############################################

    def calculate_residual_supply(
        self, vehicle_fleet: MixedSharedVehicleFleet, demand_monitor: DemandMonitor
    ) -> pd.DataFrame:
        """Calculate the fleet state: supply, low state of charge vehicles and residual supply per region.

        Parameters
        ----------
        vehicle_fleet : MixedSharedVehicleFleet
            Fleet to count vehicles in.
        demand_monitor : DemandMonitor
            Source of the observed demand per region.

        Returns
        -------
        pandas.DataFrame
            One row per region, keyed by 'hex_id', with these columns per vehicle type:

            - '<vehicle>': vehicles in the region.
            - '<vehicle>_Low_SoC': vehicles below the recharge threshold.
            - 'Inflow_<vehicle>', 'OutFlow_Fulfilled_<vehicle>', 'OutFlow_Missed_<vehicle>',
              'Delta_<vehicle>': as aggregate_delta_demand gives them.
            - 'Residual_Supply_<vehicle>': vehicles plus delta, minus low state of charge vehicles except for bikes.
        """
        # Get Vehicle Supply per Hexagon
        supply = vehicle_fleet.supply_per_region()
        supply_df = pd.DataFrame(supply).T.reset_index()
        supply_df = supply_df.rename(columns={"index": "hex_id"})

        # Get Low SoC Vehicle Supply per Hexagon
        low_soc_supply = vehicle_fleet.vehicles_to_be_charged_per_region(
            self._state_of_charge_threshold
        )
        df_low_soc = pd.DataFrame(low_soc_supply).T.reset_index()
        df_low_soc = df_low_soc.rename(columns={"index": "hex_id"})

        # Get Expected Demand (Delta) per Hexagon
        expected_demand = self.aggregate_delta_demand(demand_monitor)

        # Merge Demand, Supply and Low SoC Vehicles
        fleet_state = expected_demand.merge(supply_df, how="outer", on="hex_id")
        fleet_state = fleet_state.merge(
            df_low_soc, how="outer", on="hex_id", suffixes=("", "_Low_SoC")
        )
        fleet_state = fleet_state.fillna(0)

        # Calculate Residual Supply for each vehicle type
        for vehicle in self._available_vehicle_types:
            # TODO: Make this dependent on vehicle drive, not mode
            if vehicle == VehicleType.BIKE:
                fleet_state[f"Residual_Supply_{vehicle}"] = (
                    fleet_state[vehicle] + fleet_state[f"Delta_{vehicle}"]
                )
            else:
                fleet_state[f"Residual_Supply_{vehicle}"] = (
                    fleet_state[vehicle]
                    - (fleet_state[f"{vehicle}_Low_SoC"])
                    + fleet_state[f"Delta_{vehicle}"]
                )

        return fleet_state

    def aggregate_delta_demand(self, demand_monitor: DemandMonitor) -> pd.DataFrame:
        """
        Compute net vehicle flow (vehicle surplus or excess demand) for each hexagon and vehicle type.

        For each region (hexagon) and vehicle mode, this function calculates the net vehicle flow as the
        difference between the number of vehicles arriving (inflow) and the total outflow, where outflow
        is the sum of fulfilled departures and missed demand (unfulfilled requests). The result is a
        DataFrame with one row per hexagon and columns for inflow, fulfilled outflow, missed outflow,
        and net vehicle flow for each vehicle type.

        Parameters
        ----------
        demand_monitor : DemandMonitor
            Demand monitor containing cumulative demand statistics for each hexagon and vehicle type.

        Returns
        -------
        pd.DataFrame
            DataFrame with one row per hexagon and the following columns for each vehicle type:

            - 'Inflow_<vehicle>': int, number of vehicles arriving at the hexagon.
            - 'OutFlow_Fulfilled_<vehicle>': int, number of fulfilled departures from the hexagon.
            - 'OutFlow_Missed_<vehicle>': int, number of missed departures (unfulfilled requests)
              from the hexagon.
            - 'Delta_<vehicle>': int, net vehicle flow: inflow - outflow_fulfilled - outflow_missed.

        Notes
        -----
        - Outflow is the sum of fulfilled departures and missed demand (unfulfilled requests).
        - A negative delta indicates excess demand (more departures or missed requests than arrivals).
        - A positive delta indicates a vehicle surplus (more arrivals than departures).
        """
        vehicle_demand: VehicleDemandByRegion = demand_monitor.get_demand_data()

        rows = []
        for hex_id in sorted(vehicle_demand.keys()):
            row: dict[str, int | str] = {"hex_id": hex_id}
            for vehicle in self._available_vehicle_types:
                inflow = (
                    vehicle_demand.get(hex_id, {}).get(vehicle, {}).get("inflow", 0)
                )
                outflow_fulfilled = (
                    vehicle_demand.get(hex_id, {})
                    .get(vehicle, {})
                    .get("outflow_fulfilled", 0)
                )
                outflow_missed = (
                    vehicle_demand.get(hex_id, {})
                    .get(vehicle, {})
                    .get("outflow_missed", 0)
                )
                row[f"Inflow_{vehicle}"] = inflow
                row[f"OutFlow_Fulfilled_{vehicle}"] = outflow_fulfilled
                row[f"OutFlow_Missed_{vehicle}"] = outflow_missed
                row[f"Delta_{vehicle}"] = inflow - outflow_fulfilled - outflow_missed
            rows.append(row)
        return pd.DataFrame(rows)
