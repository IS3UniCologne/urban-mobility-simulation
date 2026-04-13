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
from simulation.helper.enums import OperatorMode, TransactionState, UserState
from simulation.helper.exceptions import ReservationCanceledError
from simulation.helper.time import SimulationVelocityConverter
from simulation.operator.data_transfer_object.transport_request import TransportRequest
from simulation.tasks.base.vehicle_session import VehicleSession
from simulation.tasks.trips.ride_hailing_trip_task import RideHailingTripTask
from simulation.tasks.trips.shared_trip_task import SharedTripTask
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle
from simulation.vehicle.shared_vehicle import SharedVehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event, Process, Timeout

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.configuration import UserConfig
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


class User(Agent):
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
    transport_task : TransportRequest
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
        "_transport_request",
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

        self._transport_request = TransportRequest(
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

    def __repr__(self) -> str:  # noqa: D105
        return f"User with id {self.uid} is in state {self._state}."

    def __str__(self) -> str:  # noqa: D105
        return f"User {self.uid}"

    @property
    def state(self) -> UserState:
        """Get the current state of the user."""
        return self._state

    @state.setter
    def state(self, value: UserState) -> None:
        """Set the current state of the user."""
        self._state = value

    @property
    def transport_request(self) -> TransportRequest:
        """Get the transport request of the user."""
        return self._transport_request

    @property
    def walking_speed_mm(self) -> float:
        """Get the walking speed of the user in meters per minute."""
        return self._walking_speed_mm

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

        while self.state not in (UserState.FULFILLED, UserState.MISSED):
            # Do we have time left to search?
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
            vehicle_allocation = yield self._env.process(
                self._try_alternatives(choice_probs)
            )
            # 4: Allocation failed for all alternatives, restart search from scratch
            if vehicle_allocation is None:
                self.logger.debug(
                    "Allocation failed for all alternatives, restarting search."
                )
                self._reset_user()
                yield self._env.timeout(1)

        self._log_trip_outcome(vehicle_allocation)
        if not self.process_finished.triggered:
            self.process_finished.succeed()

    def _try_alternatives(
        self, choice_probs: dict[TransportationAlternative, float]
    ) -> Generator[Process | Event, Any, VehicleAllocation | None]:
        """
        Try transportation alternatives probabilistically until one succeeds.

        Samples from viable alternatives (prob > 0) without replacement, attempting
        vehicle allocation for each. Returns on first success or when all alternatives
        are exhausted or the search timeout is hit.

        Parameters
        ----------
        choice_probs : dict of TransportationAlternative to float
            Mapping of alternatives to their choice probabilities.

        Yields
        ------
        Process or Event
            Allocation and trip execution processes.

        Returns
        -------
        VehicleAllocation or None
            Successful allocation, or None if all alternatives failed.
        """
        # TODO: we are attempting allocations with old information, what if the vehicle moved in the meantime?
        viable = {alt: prob for alt, prob in choice_probs.items() if prob > 0}
        attempted: set[TransportationAlternative] = set()

        while len(attempted) < len(viable):
            if self._is_search_duration_exceeded():
                self._search_end_time = self._env.now
                self.logger.debug(
                    "Max search duration reached during allocation attempts"
                )
                return None

            chosen = self._sample_alternative(viable.keys() - attempted, viable)
            attempted.add(chosen)
            self._attempted_operators.add(chosen.operator)

            vehicle_allocation: VehicleAllocation | None = yield self._env.process(
                self._allocate_vehicle(chosen)
            )

            if vehicle_allocation is None:
                continue

            self._search_end_time = self._env.now
            self._validate_allocation(vehicle_allocation, chosen)

            try:
                yield self._env.process(
                    self._execute_chosen_alternative(vehicle_allocation)
                )
            except ReservationCanceledError as err:
                self.logger.debug(
                    "Allocation canceled before trip execution for user %s on vehicle %s: %s",
                    self.uid,
                    vehicle_allocation.vehicle.uid,
                    err,
                )
                continue

            return vehicle_allocation

        return None

    def _sample_alternative(
        self,
        remaining: set[TransportationAlternative],
        viable: dict[TransportationAlternative, float],
    ) -> TransportationAlternative:
        """
        Sample one alternative from the remaining set, weighted by probability.

        Parameters
        ----------
        remaining : set of TransportationAlternative
            Alternatives not yet attempted.
        viable : dict of TransportationAlternative to float
            Full probability mapping (superset of remaining).

        Returns
        -------
        TransportationAlternative
            The sampled alternative.
        """
        alternatives_list = list(remaining)
        probs = [viable[alt] for alt in alternatives_list]
        total = sum(probs)
        normalized = [p / total for p in probs]
        idx: int = self._rng.choice(len(alternatives_list), p=normalized)
        return alternatives_list[idx]

    def _validate_allocation(
        self,
        vehicle_allocation: VehicleAllocation,
        chosen_alternative: TransportationAlternative,
    ) -> None:
        """
        Sanity-check an allocation before executing the trip.

        Parameters
        ----------
        vehicle_allocation : VehicleAllocation
            The allocation to validate.
        chosen_alternative : TransportationAlternative
            The alternative that was allocated.

        Raises
        ------
        RuntimeError
            If any sanity check fails.
        """
        reservation = vehicle_allocation.reservation
        if reservation is None:
            raise RuntimeError("Sanity check failed: allocation has no reservation")
        if reservation.requester is not self:
            raise RuntimeError(
                "Sanity check failed: allocation reservation requester mismatch"
            )

        required_distance = chosen_alternative.distance + (
            chosen_alternative.route_to_pickup.distance
            if chosen_alternative.route_to_pickup
            else 0.0
        )
        if not vehicle_allocation.vehicle.energy_system.has_enough_energy(
            required_distance
        ):
            raise RuntimeError(
                "Sanity check failed: allocation granted despite insufficient energy "
                f"for required_distance={required_distance:.2f}m"
            )

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
                origin=self._transport_request.origin.get_region_id(),
                destination=self._transport_request.destination.get_region_id(),
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
                origin=self._transport_request.origin.get_region_id(),
                destination=self._transport_request.destination.get_region_id(),
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
                    self._transport_request
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
    ) -> Generator[Event | Process, Any, None]:
        """Execute the selected transportation alternative via VehicleSession.

        Creates the appropriate trip task, wraps it in a VehicleSession,
        and executes. The session manages the reservation lifecycle.

        Parameters
        ----------
        vehicle_allocation : VehicleAllocation
            The vehicle allocation for the trip.

        Yields
        ------
        Event or Process
            Simulation events and processes for trip execution.

        Raises
        ------
        NotImplementedError
            If the operator mode is not supported.
        """
        operator_mode = vehicle_allocation.transportation_alternative.operator.mode

        self._trip_start_time = self._env.now

        trip_task: RideHailingTripTask | SharedTripTask

        if operator_mode == OperatorMode.RIDE_HAILING:
            vehicle = vehicle_allocation.vehicle
            assert isinstance(vehicle, RideHailingVehicle)
            trip_task = RideHailingTripTask(
                sim=self._sim, vehicle=vehicle, user=self, allocation=vehicle_allocation
            )
        elif operator_mode == OperatorMode.SHARED_MOBILITY:
            vehicle = vehicle_allocation.vehicle
            assert isinstance(vehicle, SharedVehicle)
            trip_task = SharedTripTask(
                sim=self._sim, vehicle=vehicle, user=self, allocation=vehicle_allocation
            )
        elif operator_mode == OperatorMode.PUBLIC_TRANSPORT:
            # Public transport not yet migrated to VehicleSession
            yield self._env.process(self._walk_to_transit_stop(vehicle_allocation))
            yield self._env.process(self._wait_for_transport(vehicle_allocation))
            return
        else:
            raise NotImplementedError(f"Operator mode {operator_mode} not supported")

        # Execute trip via VehicleSession
        reservation = vehicle_allocation.reservation
        assert reservation is not None
        session = VehicleSession(
            sim=self._sim,
            vehicle=vehicle_allocation.vehicle,
            reservation=reservation,
            tasks=[trip_task],
            holder=self,
        )
        yield from session.execute()

        # Retrieve results from trip task
        trip_energy = trip_task.energy_consumed
        vehicle_allocation.increase_energy_consumed(trip_energy)
        self._energy_consumed += trip_energy

        # Record timing
        if isinstance(trip_task, RideHailingTripTask):
            arrival_time = trip_task.vehicle_arrival_time
            if arrival_time is not None:
                self._vehicle_arrival_time = arrival_time
        self._assigned_vehicle_arrived.succeed()
        self._arrived_at_destination.succeed()

        self.state = UserState.FULFILLED
        self.logger.debug("Trip completed.")

        # Store trip end time and handle payment
        self._trip_end_time = self._env.now
        operator = vehicle_allocation.transportation_alternative.operator
        operator.pay_for_fulfilled_transportation_task(
            user=self,
            transportation_task=self._transport_request,
            vehicle_allocation=vehicle_allocation,
        )

    def walk_to(self, destination: GeodesicPosition) -> Generator[Timeout, Any, None]:
        """Walk from current position to a destination.

        Parameters
        ----------
        destination : GeodesicPosition
            Target position to walk to.

        Yields
        ------
        Timeout
            Timeout event corresponding to walking duration.
        """
        yield from self._walk(self._position, destination)

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
        distance = origin << destination
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
    def on_vehicle_moved(self, position: GeodesicPosition) -> None:
        """Update position when the vehicle carrying this user moves.

        Parameters
        ----------
        position : GeodesicPosition
            The new position of the vehicle.
        """
        self._position = position
