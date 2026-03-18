"""User agent for modeling individual mobility behavior in the simulation.

Users autonomously search for transportation options, make decisions based
on configurable choice models, and execute trips through different mobility
services (ride-hailing, shared vehicles, public transport).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from simulation.agent.agent import Agent
from simulation.agent.user.choice_model import ChoiceModelInterface
from simulation.agent.user.choice_model.choice_model_interface import (
    ChoiceModelDependencies,
)
from simulation.agent.user.user_log import (
    FulfilledUserLogEntry,
    MissedUserLogEntry,
    UserLog,
    UserLogEntry,
)
from simulation.helper.configuration.enums import (
    OperatorMode,
    TransactionState,
    UserState,
)
from simulation.helper.time import SimulationVelocityConverter
from simulation.tasks.transport_task import TransportTask
from simulation.vehicle.interfaces.driver_interface import DriverInterface
from simulation.vehicle.interfaces.passenger_interface import PassengerInterface
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle
from simulation.vehicle.shared_vehicle import SharedVehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event, Process, Timeout

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import UserConfig
    from simulation.infrastructure.route import Route
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.transportation_alternative_browser import (
        TransportationAlternativeBrowser,
    )
    from simulation.operator.data_transfer_object.vehicle_allocation import (
        VehicleAllocation,
    )
    from simulation.operator.interface.operator_interface import OperatorInterface
    from simulation.world.mobility_search_engine import MobilitySearchEngine


class User(Agent, DriverInterface, PassengerInterface):
    """
    Represents a single user agent in the simulation.

    User behaviour is mainly defined by the run() method, which implements the lifecycle
    of searching for transportation alternatives, making choices, and executing trips.

    Each user has a transport task defining their origin and destination,
    and uses a choice model to select among available transportation alternatives.

    Each user will only complete a single trip. Once the transport task is fulfilled or missed,
    the user lifecycle ends and the user is removed from the simulation.

    Parameters
    ----------
    sim : SimulationContext
        The simulation context.
    user_config : UserConfig
        Configuration for the user.
    user_log : UserLog
        Logger for user outcomes.
    origin : GeodesicPosition
        The starting position of the user.
    destination : GeodesicPosition
        The destination of the user.
    mobility_search_engine : MobilitySearchEngine
        Engine to search for mobility options.

    Attributes
    ----------
    state : UserState
        Current state of the user.
    transport_task : TransportTask
        The transportation task associated with the user.
    energy_consumed : float
        Total energy consumed by the user.
    """

    __slots__ = (
        "_arrived_at_destination",
        "_arrived_at_stop_time",
        "_assigned_vehicle_arrived",
        "_attempted_operators",
        "_choice_model",
        "_destination",
        "_energy_consumed",
        "_env",
        "_max_search_duration_min",
        "_mobility_search_engine",
        "_origin",
        "_position",
        "_rng",
        "_run_process",
        "_search_end_time",
        "_search_start_time",
        "_sim",
        "_state",
        "_transport_task",
        "_transportation_alternatives_not_found",
        "_trip_end_time",
        "_trip_start_time",
        "_user_log",
        "_vehicle_allocated",
        "_vehicle_allocation_time",
        "_vehicle_arrival_time",
        "_walking_speed_mm",
        "process_finished",
    )

    def __init__(
        self,
        sim: SimulationContext,
        user_config: UserConfig,
        user_log: UserLog,
        origin: GeodesicPosition,
        destination: GeodesicPosition,
        mobility_search_engine: MobilitySearchEngine,
    ) -> None:
        super().__init__(sim)
        self._sim = sim
        self._user_log = user_log
        self._env = self._sim.env
        self._rng = sim.random_manager.get_rng("MODE_CHOICE_MODEL")

        self._position = origin
        self._origin = origin
        self._destination = destination

        self._mobility_search_engine = mobility_search_engine
        self._choice_model: ChoiceModelInterface = ChoiceModelInterface.from_deps(
            deps=ChoiceModelDependencies(
                sim=self._sim, choice_model_config=user_config.CHOICE_MODEL_CONFIG
            )
        )

        self._max_search_duration_min = user_config.MAX_SEARCH_DURATION_MIN
        self._walking_speed_mm = SimulationVelocityConverter.kmh_to_meters_per_minute(
            user_config.WALKING_SPEED_KMH
        )

        self._transport_task = TransportTask(
            creation_time=self._sim.env.now,
            origin=origin,
            destination=destination,
            accepted_vehicle_types=self._choice_model.accepted_vehicle_types,
        )

        ### Runtime Variables ###

        # Track operators attempted and successful operator for global logging
        self._attempted_operators: set[OperatorInterface] = set()
        self._trip_start_time: float
        self._trip_end_time: float
        self._vehicle_allocation_time: float
        self._vehicle_arrival_time: float
        self._arrived_at_stop_time: float
        self._energy_consumed: float = 0.0

        ### Events and Processes ###
        # Events used for coordination and logging
        self._transportation_alternatives_not_found = self._env.event()
        self._vehicle_allocated = self._env.event()
        self._assigned_vehicle_arrived = self._env.event()
        self._arrived_at_destination = self._env.event()

        self.process_finished = self._env.event()

        self._run_process: Process | None = None

        ### Initialization complete ###
        self._state = UserState.INITIALIZED
        self.logger.debug("Initialized.")

    def start(self) -> None:
        """Start the user's lifecycle process."""
        if self._run_process is not None:
            self.logger.warning("Attempted to start user process multiple times.")
            return

        self._run_process = self._env.process(self.run())

        self.logger.debug("Started user process.")

    def __str__(self) -> str:
        """Return string representation of the user."""
        return f"User with id {self.uid} is in state {self._state} and has transportation task {self._transport_task}"

    @property
    def state(self) -> UserState:
        """Get the current state of the user."""
        return self._state

    @state.setter
    def state(self, value: UserState) -> None:
        """Set the current state of the user."""
        self._state = value

    @property
    def transport_task(self) -> TransportTask:
        """Get the transport task of the user."""
        return self._transport_task

    @property
    def energy_consumed(self) -> float:
        """Get the total energy consumed by the user's activities."""
        return self._energy_consumed

    def run(self) -> Generator[Process | Timeout, Any, None]:
        """
        Full user lifecycle.

        Yields
        ------
        Process or Timeout
            User events and processes.
        """
        self._search_start_time = self._env.now
        vehicle_allocation: VehicleAllocation | None = None

        while self.state != UserState.FULFILLED and self.state != UserState.MISSED:
            # Does we have time left to search?
            if self._is_search_duration_exceeded():
                self._search_end_time = self._env.now
                self.state = UserState.MISSED
                self.logger.debug("Exceeded max search duration.")
                break

            # 1: Search trip alternatives
            available_alternatives = yield self._env.process(
                self._search_for_alternatives()
            )

            if not available_alternatives.transportation_alternatives:
                break

            # 2: Calculate choice probabilities using choice model
            choice_probs: dict[TransportationAlternative, float] = (
                self._calculate_choice_probabilities(available_alternatives)
            )

            # 3: Try alternatives probabilistically until one succeeds or we run out of time
            attempted_alternatives: set[TransportationAlternative] = set()
            allocation_succeeded = False
            viable_alternatives = {
                alt: prob for alt, prob in choice_probs.items() if prob > 0
            }
            viable_alternatives_set = set(viable_alternatives.keys())

            while (
                len(attempted_alternatives) < len(viable_alternatives)
                and not allocation_succeeded
            ):
                # TODO: we are attempting allocations with old information, what if the vehicle moved in the meantime?
                # Check timeout before attempting allocation
                if self._is_search_duration_exceeded():
                    self._search_end_time = self._env.now
                    self.logger.debug(
                        "Max search duration reached during allocation attempts"
                    )
                    break

                remaining_alts = viable_alternatives_set - attempted_alternatives

                # Sample and try
                alternatives_list = list(remaining_alts)
                probabilities = [viable_alternatives[alt] for alt in alternatives_list]
                total_prob = sum(probabilities)
                normalized_probs = [p / total_prob for p in probabilities]

                chosen_idx: int = self._rng.choice(
                    len(alternatives_list), p=normalized_probs
                )
                chosen_alternative = alternatives_list[chosen_idx]

                attempted_alternatives.add(chosen_alternative)

                # Track that we attempted this operator
                self._attempted_operators.add(chosen_alternative.operator)

                # TODO: check if this solves multiple allocations in ride hailing case, need to establish real reservation system
                chosen_alternative.vehicle._suggested = True  # noqa: SLF001

                # Attempt allocation
                vehicle_allocation = yield self._env.process(
                    self._allocate_vehicle(chosen_alternative)
                )

                if vehicle_allocation:
                    # We found a viable alternative, execute the trip
                    self._search_end_time = self._env.now
                    yield self._env.process(
                        self._execute_chosen_alternative(vehicle_allocation)
                    )
                    allocation_succeeded = True

            # 4: Allocation failed for all alternatives, restart search from scratch
            if not allocation_succeeded:
                self.logger.debug(
                    "Allocation failed for all alternatives, restarting search."
                )
                self._reset_user()
                yield self._env.timeout(1)
                continue

        # Log final outcome
        self._log_trip_outcome(vehicle_allocation)

        # Ensure process is always marked as finished
        if not self.process_finished.triggered:
            self.process_finished.succeed()

    def _log_trip_outcome(self, vehicle_allocation: VehicleAllocation | None) -> None:
        """
        Log the final trip outcome to the UserLog.

        Parameters
        ----------
        vehicle_allocation : VehicleAllocation or None
            The vehicle allocation if the trip was fulfilled, else None.
        """
        attempted_operator_uids = [op.uid for op in self._attempted_operators]

        outcome: UserLogEntry
        if self.state == UserState.FULFILLED:
            if vehicle_allocation is None:
                raise ValueError(
                    "Vehicle allocation must be provided for fulfilled trips"
                )

            # Calculate actual wait time
            actual_wait_time = self._calculate_actual_wait_time(vehicle_allocation)

            outcome = FulfilledUserLogEntry(
                user_uid=self.uid,
                origin=self._transport_task.origin.get_region_id(),
                destination=self._transport_task.destination.get_region_id(),
                search_start_time=self._search_start_time,
                search_end_time=self._search_end_time,
                outcome_time=self._env.now,
                attempted_operator_uids=attempted_operator_uids,
                outcome_state=TransactionState.FULFILLED,
                fulfilled_by_operator_uid=vehicle_allocation.transportation_alternative.operator.uid,
                vehicle_uid=vehicle_allocation.vehicle.uid,
                vehicle_type=vehicle_allocation.vehicle.vehicle_type,
                actual_wait_time=actual_wait_time,
                trip_start_time=self._trip_start_time,
                trip_end_time=self._trip_end_time,
                energy_consumed=self._energy_consumed,
                price_paid=vehicle_allocation.transportation_alternative.price,
            )
        else:
            outcome = MissedUserLogEntry(
                user_uid=self.uid,
                origin=self._transport_task.origin.get_region_id(),
                destination=self._transport_task.destination.get_region_id(),
                search_start_time=self._search_start_time,
                search_end_time=self._search_end_time,
                outcome_time=self._env.now,
                attempted_operator_uids=attempted_operator_uids,
                outcome_state=TransactionState.MISSED,
            )

        self._user_log.log_trip_outcome(outcome)

    def _calculate_actual_wait_time(
        self, vehicle_allocation: VehicleAllocation
    ) -> float:
        """
        Calculate actual wait time based on operator mode.

        Parameters
        ----------
        vehicle_allocation : VehicleAllocation
            The vehicle allocation containing operator and timing info.

        Returns
        -------
        float
            The calculated wait time in minutes.

        Raises
        ------
        NotImplementedError
            If the operator mode is not supported.
        """
        operator_mode = vehicle_allocation.transportation_alternative.operator.mode

        if operator_mode == OperatorMode.RIDE_HAILING:
            # Wait time from allocation to vehicle arrival
            return self._vehicle_arrival_time - self._vehicle_allocation_time
        elif operator_mode == OperatorMode.PUBLIC_TRANSPORT:
            # Wait time at transit stop

            return self._vehicle_arrival_time - self._arrived_at_stop_time
        elif operator_mode == OperatorMode.SHARED_MOBILITY:
            # No wait time for shared mobility (vehicle is already there)
            return 0.0
        else:
            raise NotImplementedError(
                f"Operator mode {operator_mode} not implemented in wait time calculation."
            )

    def _is_search_duration_exceeded(self) -> bool:
        """
        Check if the search duration has exceeded the maximum allowed time.

        Returns
        -------
        bool
            True if search duration exceeded, False otherwise.
        """
        return self._env.now - self._search_start_time > self._max_search_duration_min

    def _reset_user(self) -> None:
        """Reset user events."""
        self._transportation_alternatives_not_found = self._env.event()
        self._vehicle_allocated = self._env.event()

    def _search_for_alternatives(
        self,
    ) -> Generator[Timeout, Any, TransportationAlternativeBrowser]:
        """
        User searches for transportation alternatives using the mobility search engine.

        Yields
        ------
        Timeout
            Timeout event for search duration.

        Returns
        -------
        TransportationAlternativeBrowser
            The found transportation alternatives.
        """
        while True:
            self.state = UserState.SEARCHING_TRANSPORT_ALTERNATIVES

            available_transportation_alternatives = (
                self._mobility_search_engine.search_for_transportation_alternatives(
                    self._transport_task
                )
            )

            self.logger.debug(
                "Received %s transportation alternatives",
                len(available_transportation_alternatives.transportation_alternatives),
            )

            if (
                len(available_transportation_alternatives.transportation_alternatives)
                >= 1
            ):
                # Break the loop if we found at least one alternative
                return available_transportation_alternatives

            if self._is_search_duration_exceeded():
                self._search_end_time = self._env.now
                self.state = UserState.MISSED
                self.logger.debug("Exceeded max search duration.")
                break

            # Wait before searching again
            yield self._env.timeout(1)

        # We did not receive any transportation alternatives, return empty list
        self._transportation_alternatives_not_found.succeed()
        return available_transportation_alternatives

    def _execute_chosen_alternative(
        self, vehicle_allocation: VehicleAllocation
    ) -> Generator[Process, Any, None]:
        """
        User executes the selected transportation alternative.

        Parameters
        ----------
        vehicle_allocation : VehicleAllocation
            The vehicle allocation for the trip.

        Yields
        ------
        Process
            Simulation processes for trip execution.

        Raises
        ------
        NotImplementedError
            If the operator mode is not supported.
        """
        operator_mode = vehicle_allocation.transportation_alternative.operator.mode

        self._trip_start_time = self._env.now

        # 1: Move to vehicle / wait for vehicle arrival
        if operator_mode == OperatorMode.RIDE_HAILING:
            yield self._env.process(self._wait_for_vehicle_arrival(vehicle_allocation))
        elif operator_mode == OperatorMode.SHARED_MOBILITY:
            yield self._env.process(self._walk_to_vehicle(vehicle_allocation))
        elif operator_mode == OperatorMode.PUBLIC_TRANSPORT:
            yield self._env.process(self._walk_to_transit_stop(vehicle_allocation))
            yield self._env.process(self._wait_for_transport(vehicle_allocation))
        else:
            raise NotImplementedError(f"Operator mode {operator_mode} not supported")

        # 2: Execute trip
        trip_energy = yield self._env.process(
            self._start_trip(vehicle_allocation=vehicle_allocation)
        )
        vehicle_allocation.increase_energy_consumed(trip_energy)
        self._energy_consumed += trip_energy

        # 3: Store trip execution details for global logging
        self._trip_end_time = self._env.now
        # 4: Handle payment
        operator = vehicle_allocation.transportation_alternative.operator
        operator.pay_for_fulfilled_transportation_task(
            user=self,
            transportation_task=self._transport_task,
            vehicle_allocation=vehicle_allocation,
        )

    def _wait_for_vehicle_arrival(
        self, vehicle_allocation: VehicleAllocation
    ) -> Generator[Any, Any, None]:
        """
        Wait for a ride-hailing vehicle to arrive at user's location.

        Parameters
        ----------
        vehicle_allocation : VehicleAllocation
            The vehicle allocation.

        Yields
        ------
        Any
            Event indicating vehicle arrival.

        Raises
        ------
        ValueError
            If the vehicle is not a ride-hailing vehicle.
        """
        self._state = UserState.WAITING_FOR_VEHICLE

        # TODO: Make this cleaner
        # check if vehicle is a ride hailing vehicle
        if not isinstance(vehicle_allocation.vehicle, RideHailingVehicle):
            raise ValueError("Vehicle is not a ride-hailing vehicle")

        # Wait for vehicle to arrive at pickup position
        yield vehicle_allocation.vehicle._arrived_at_pick_up_position  # noqa: SLF001

        self._vehicle_arrival_time = self._env.now
        self._assigned_vehicle_arrived.succeed()
        self.logger.debug(
            "Vehicle %s arrived at user location at time %s.",
            vehicle_allocation.vehicle.uid,
            self._env.now,
        )

    def _walk_to_vehicle(
        self, vehicle_allocation: VehicleAllocation
    ) -> Generator[Process, Any, None]:
        """
        Walk to a shared vehicle's parking location.

        Parameters
        ----------
        vehicle_allocation : VehicleAllocation
            The vehicle allocation.

        Yields
        ------
        Process
            Walking process.
        """
        self._state = UserState.MOVING_TO_VEHICLE

        # Walk to where the vehicle is parked
        yield self._env.process(
            self._walk(self._position, vehicle_allocation.pick_up_position)
        )

        self.logger.debug(
            "Arrived at vehicle %s at position %s at time %s.",
            vehicle_allocation.vehicle.uid,
            vehicle_allocation.pick_up_position,
            self._env.now,
        )

        # Vehicle is immediately available (no waiting)
        self._assigned_vehicle_arrived.succeed()

    def _walk_to_transit_stop(
        self, vehicle_allocation: VehicleAllocation
    ) -> Generator[Process, Any, None]:
        """
        Walk to a public transit stop.

        Parameters
        ----------
        vehicle_allocation : VehicleAllocation
            The vehicle allocation.

        Yields
        ------
        Process
            Walking process.
        """
        self._state = UserState.MOVING_TO_TRANSPORT_STOP

        yield self._env.process(
            self._walk(self._position, vehicle_allocation.pick_up_position)
        )

        self._arrived_at_stop_time = self._env.now

        self.logger.debug(
            "Arrived at public transport stop at %s at time %s.",
            vehicle_allocation.pick_up_position,
            self._env.now,
        )

    def _wait_for_transport(
        self, vehicle_allocation: VehicleAllocation
    ) -> Generator[Any, Any, None]:
        """
        Wait for public transport vehicle to arrive at stop.

        Parameters
        ----------
        vehicle_allocation : VehicleAllocation
            The vehicle allocation.

        Yields
        ------
        Any
            Event indicating transport arrival.

        Raises
        ------
        NotImplementedError
            Always, as this is not implemented yet.
        """
        self._state = UserState.WAITING_FOR_TRANSPORT

        # TODO: Logic for waiting for transport arrival

        raise NotImplementedError("Waiting for transport not implemented yet.")

        # self._assigned_vehicle_arrived.succeed()

    def _start_trip(
        self, vehicle_allocation: VehicleAllocation
    ) -> Generator[Process | Timeout, Any, float]:
        """
        Start the trip with the allocated vehicle.

        Parameters
        ----------
        vehicle_allocation : VehicleAllocation
            The vehicle allocation.

        Yields
        ------
        Process or Timeout
            Driving or riding process.

        Returns
        -------
        float
            Energy consumed during the trip.

        Raises
        ------
        NotImplementedError
            If the vehicle type is not supported.
        """
        vehicle = vehicle_allocation.vehicle
        route = vehicle_allocation.transportation_alternative.route
        energy_consumed: float = 0.0

        if isinstance(vehicle, RideHailingVehicle):
            # Mount vehicle as passenger
            self.state = UserState.IN_TRANSPORT
            self.mount_vehicle(vehicle)

            # Vehicle drives to destination
            energy_consumed = yield self._env.process(
                generator=self.ride_in_vehicle(vehicle, route)
            )

            self.park_vehicle(vehicle)  # type: ignore #TODO: This should not be done by the user
            self.unmount_vehicle(vehicle)

        elif isinstance(vehicle, SharedVehicle):
            # For shared vehicles, user acts as driver
            self.state = UserState.IN_TRANSPORT
            self.mount_vehicle_as_driver(vehicle)

            # User drives vehicle to destination
            energy_consumed = yield self._env.process(
                self.drive_vehicle(vehicle, route)
            )

            self.park_vehicle(vehicle)
            self.unmount_vehicle_as_driver(vehicle)

        else:
            raise NotImplementedError(f"Vehicle type {type(vehicle)} not supported")

        self._arrived_at_destination.succeed()
        self.state = UserState.FULFILLED
        self.logger.debug("Trip completed.")
        return energy_consumed

    def _walk(
        self, origin: GeodesicPosition, destination: GeodesicPosition
    ) -> Generator[Timeout, Any, None]:
        """
        Simulate walking from origin to destination.

        Parameters
        ----------
        origin : GeodesicPosition
            Starting position.
        destination : GeodesicPosition
            Target position.

        Yields
        ------
        Timeout
            Timeout event corresponding to walking duration.
        """
        distance = origin >> destination
        duration = distance / self._walking_speed_mm

        self.logger.debug(
            "Walking from %s to %s. Distance: %s meters, duration: %s minutes.",
            origin,
            destination,
            distance,
            duration,
        )
        yield self._env.timeout(duration)
        self._position = destination

    def _allocate_vehicle(
        self, selected_transportation_alternative: TransportationAlternative
    ) -> Generator[Process, Any, VehicleAllocation | None]:
        """
        Request vehicle allocation for the selected transportation alternative.

        Parameters
        ----------
        selected_transportation_alternative : TransportationAlternative
            The selected alternative to request allocation for.

        Yields
        ------
        Process
            Allocation process.

        Returns
        -------
        VehicleAllocation or None
            The allocated vehicle if successful, None otherwise.
        """
        # Set current state
        self.state = UserState.AWAITING_ALLOCATION

        # Get Vehicle Allocation
        vehicle_allocation: VehicleAllocation | None = yield self._env.process(
            selected_transportation_alternative.operator.allocation_engine.request_vehicle_allocation(
                self, selected_transportation_alternative
            )  # TODO: funny, maybe encapsulate in TransportationAlternative
        )

        # Vehicle was successfully allocated to request
        if vehicle_allocation:
            self._vehicle_allocation_time = self._env.now
            self._vehicle_allocated.succeed()

            self.logger.debug(
                "Vehicle %s has been allocated.", vehicle_allocation.vehicle.uid
            )
            return vehicle_allocation
        else:
            self.logger.debug("No vehicle was allocated.")
            return None

    def _calculate_choice_probabilities(
        self, available_alternatives: TransportationAlternativeBrowser
    ) -> dict[TransportationAlternative, float]:
        """
        Calculate choice probabilities using the configured choice model.

        Parameters
        ----------
        available_alternatives : TransportationAlternativeBrowser
            Available transportation alternatives.


        Returns
        -------
        dict of TransportationAlternative to float
            Mapping of alternatives to their choice probabilities (sum to 1.0).
        """
        # Calculate choice probabilities using the choice model
        choice_probs = self._choice_model.calculate_choice_probabilities(
            user=self, available_alternatives=available_alternatives
        )

        self.logger.debug(
            "Calculated choice probabilities for %d alternatives.", len(choice_probs)
        )

        return choice_probs

    # --------------------------
    # DriverInterface
    # --------------------------
    def mount_vehicle_as_driver(self, vehicle: SharedVehicle) -> None:
        """
        Mount vehicle as driver.

        TODO: Create DrivableVehicleInterface to generalize this

        Parameters
        ----------
        vehicle : SharedVehicle
            The vehicle to mount.
        """
        vehicle.mount_driver(self)

    def drive_vehicle(
        self, vehicle: SharedVehicle, route: Route
    ) -> Generator[Event, Any, float]:
        """
        Drive vehicle along route.

        TODO: Create DrivableVehicleInterface to generalize this

        Parameters
        ----------
        vehicle : SharedVehicle
            The vehicle to drive.
        route : Route
            The route to follow.

        Yields
        ------
        Event
            Driving process events.

        Returns
        -------
        float
            Energy consumed.
        """
        vehicle.start_driving()
        energy_consumed = yield from vehicle.traverse_route(route)

        vehicle.stop_driving()
        return energy_consumed

    def park_vehicle(self, vehicle: SharedVehicle) -> None:
        """
        Park vehicle.

        Parameters
        ----------
        vehicle : SharedVehicle
            The vehicle to park.
        """
        vehicle.park()

    def unmount_vehicle_as_driver(self, vehicle: SharedVehicle) -> None:
        """
        Unmount vehicle as driver.

        Parameters
        ----------
        vehicle : SharedVehicle
            The vehicle to unmount.
        """
        vehicle.unmount_driver()

    # TODO : Probably can get rid of this
    def identify_driver(self) -> str:
        """
        Identify driver.

        Returns
        -------
        str
            Driver identifier.
        """
        return f"User {self.uid}"

    # --------------------------
    # PassengerInterface
    # --------------------------
    def mount_vehicle(self, vehicle: RideHailingVehicle) -> None:
        """
        Mount vehicle as a passenger.

        Parameters
        ----------
        vehicle : RideHailingVehicle
            The vehicle to mount.
        """
        vehicle.mount_passenger(self)

    def unmount_vehicle(self, vehicle: RideHailingVehicle) -> None:
        """
        Unmount vehicle as a passenger.

        Parameters
        ----------
        vehicle : RideHailingVehicle
            The vehicle to unmount.
        """
        vehicle.unmount_passenger(self)

    def ride_in_vehicle(
        self, vehicle: RideHailingVehicle, route: Route
    ) -> Generator[Event, Any, float]:
        """
        Ride in vehicle as a passenger.

        TODO: user currently acts as driver, need to change that

        Parameters
        ----------
        vehicle : RideHailingVehicle
            The vehicle to ride in.
        route : Route
            The route to follow.

        Yields
        ------
        Event
            Riding process events.

        Returns
        -------
        float
            Energy consumed.
        """
        vehicle.start_driving()
        energy_consumed = yield from vehicle.traverse_route(route)

        vehicle.stop_driving()

        return energy_consumed

    # TODO : Probably can get rid of this
    def identify_passenger(self) -> str:
        """
        Identify passenger.

        Returns
        -------
        str
            Passenger identifier.
        """
        return f"User {self.uid}"
