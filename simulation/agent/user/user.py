"""User agent for modeling individual mobility behavior in the simulation.

Users autonomously search for transportation options, make decisions based
on configurable choice models, and execute trips through different mobility
services (ride-hailing, shared vehicles, public transport).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from simulation.agent.agent import Agent
from simulation.agent.user.choice_model.random_nearest_vehicle_choice_model import (
    RandomModeNearestVehicleChoiceModel,
)
from simulation.helper.configuration.enums import (
    OperatorMode,
    TransactionState,
    UserState,
)
from simulation.helper.time import SimulationVelocityConverter
from simulation.vehicle.interfaces.driver_interface import DriverInterface
from simulation.vehicle.interfaces.passenger_interface import PassengerInterface
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle
from simulation.vehicle.shared_vehicle import SharedVehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Process, Timeout

    from simulation.agent.user.choice_model import ChoiceModelInterface
    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.geodesic_position import GeodesicPosition
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
    from simulation.tasks.transport_task import TransportTask
    from simulation.world.mobility_search_engine import MobilitySearchEngine


class User(Agent, DriverInterface, PassengerInterface):
    """Represents a single user agent in the simulation.

    User behaviour is mainly defined by the run() method, which implements the lifecycle
    of searching for transportation alternatives, making choices, and executing trips.

    Each user has a transport task defining their origin and destination,
    and uses a choice model to select among available transportation alternatives.

    Each user will only complete a single trip. Once the transport task is fulfilled or missed,
    the user lifecycle ends and the user is removed from the simulation.
    """

    def __init__(
        self,
        sim: SimulationContext,
        position: GeodesicPosition,
        transport_task: TransportTask,
        mobility_search_engine: MobilitySearchEngine,
        choice_model: ChoiceModelInterface | None = None,
    ) -> None:
        super().__init__(sim)

        self._sim = sim
        self._env = self._sim.env
        self._rng = sim.random_manager.get_rng("MODE_CHOICE_MODEL")

        self._position = position
        self._transport_task = transport_task

        self._mobility_search_engine = mobility_search_engine
        if choice_model is None:
            self._choice_model: ChoiceModelInterface = (
                RandomModeNearestVehicleChoiceModel(sim)  # TODO: From config
            )
        else:
            self._choice_model = choice_model

        self._max_search_duration_min = 10  # TODO: From config
        self._walking_speed_kmh = 5  # km/h,#TODO: From config

        ### Runtime Variables ###

        # How long we've searched so far
        self._elapsed_search_duration = 0.0
        ### Events and Processes ###
        # TODO: Clean up unused events
        self._transportation_alternatives_selected = self._env.event()
        self._transportation_alternatives_not_found = self._env.event()
        self._transportation_alternatives_refused = self._env.event()
        self._vehicle_allocated = self._env.event()
        self._arrived_at_pick_up_position = self._env.event()
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

    def run(self) -> Generator[Process | Timeout, Any, None]:
        """Full user lifecycle."""
        self._search_start_time = self._env.now

        while self.state != UserState.FULFILLED and self.state != UserState.MISSED:
            # Does we have time left to search?
            if self._is_search_duration_exceeded():
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
            choice_probs: dict[
                TransportationAlternative, float
            ] = yield self._env.process(
                self._calculate_choice_probabilities(available_alternatives)
            )

            # 3: Try alternatives probabilistically until one succeeds or we run out of time
            attempted_alternatives: set[TransportationAlternative] = set()
            allocation_succeeded = False
            viable_alternatives = {
                alt: prob for alt, prob in choice_probs.items() if prob > 0
            }

            while (
                len(attempted_alternatives) < len(choice_probs)
                and not allocation_succeeded
            ):
                # Check timeout before attempting allocation
                if self._is_search_duration_exceeded():
                    self.logger.debug(
                        "Max search duration reached during allocation attempts"
                    )
                    break

                remaining = {
                    alt: prob
                    for alt, prob in viable_alternatives.items()
                    if alt not in attempted_alternatives
                }

                if not remaining:
                    break

                # Sample and try
                alternatives_list = list(remaining.keys())
                probabilities = list(remaining.values())
                total_prob = sum(probabilities)
                normalized_probs = [p / total_prob for p in probabilities]

                chosen_idx: int = self._rng.choice(
                    len(alternatives_list), p=normalized_probs
                )
                chosen_alternative = alternatives_list[chosen_idx]

                attempted_alternatives.add(chosen_alternative)

                # Attempt allocation
                vehicle_allocation = yield self._env.process(
                    self._allocate_vehicle(chosen_alternative)
                )

                if vehicle_allocation:
                    # We found a viable alternative, execute the trip
                    self._elapsed_search_duration += (
                        self._env.now - self._search_start_time
                    )
                    yield self._env.process(
                        self._execute_chosen_alternative(vehicle_allocation)
                    )
                    allocation_succeeded = True
                else:
                    # TODO: Instead of generating the missed transaction here, we could have the operator do it when allocation fails
                    chosen_alternative.operator.withdraw_transportation_task(
                        self, self._transport_task, state=TransactionState.MISSED
                    )

            # 4: Allocation failed for all alternatives, restart search from scratch
            if not allocation_succeeded:
                self.logger.debug(
                    "Allocation failed for all alternatives, restarting search."
                )
                self._reset_user()
                yield self._env.timeout(1)
                continue

        # Ensure process is always marked as finished
        if not self.process_finished.triggered:
            self.process_finished.succeed()

    def _is_search_duration_exceeded(self) -> bool:
        return self._env.now - self._search_start_time > self._max_search_duration_min

    def _reset_user(self) -> None:
        """Reset user events."""
        self._transportation_alternatives_selected = self._env.event()
        self._transportation_alternatives_refused = self._env.event()
        self._transportation_alternatives_not_found = self._env.event()
        self._vehicle_allocated = self._env.event()

    def _search_for_alternatives(
        self,
    ) -> Generator[Timeout, Any, TransportationAlternativeBrowser]:
        """User searches for transportation alternatives using the mobility search engine."""
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
        """
        operator_mode = (
            vehicle_allocation.associated_transportation_alternative.operator.mode
        )

        trip_start_time = self._env.now
        wait_time = trip_start_time - self._search_start_time

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
        yield self._env.process(
            self._start_trip(vehicle_allocation=vehicle_allocation, wait_time=wait_time)
        )

        # 3: Update transport task with wait time
        self._transport_task.actual_wait_time = wait_time

        # 4: Handle payment
        operator = vehicle_allocation.associated_transportation_alternative.operator
        operator.pay_for_fulfilled_transportation_task(
            user=self,
            transportation_task=self._transport_task,
            selected_transportation_alternative=vehicle_allocation.associated_transportation_alternative,
        )

    def _wait_for_vehicle_arrival(
        self, vehicle_allocation: VehicleAllocation
    ) -> Generator[Any, Any, None]:
        """Wait for a ride-hailing vehicle to arrive at user's location."""
        self._state = UserState.WAITING_FOR_VEHICLE

        # TODO: Make this cleaner
        # check if vehicle is a ride hailing vehicle
        if not isinstance(vehicle_allocation.vehicle, RideHailingVehicle):
            raise ValueError("Vehicle is not a ride-hailing vehicle")

        # Wait for vehicle to arrive at pickup position
        yield vehicle_allocation.vehicle._arrived_at_pick_up_position  # noqa: SLF001

        self._assigned_vehicle_arrived.succeed()
        self.logger.debug(
            "Vehicle %s arrived at user location at time %s.",
            vehicle_allocation.vehicle.uid,
            self._env.now,
        )

    def _walk_to_vehicle(
        self, vehicle_allocation: VehicleAllocation
    ) -> Generator[Process, Any, None]:
        """Walk to a shared vehicle's parking location."""
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
        """Walk to a public transit stop."""
        self._state = UserState.MOVING_TO_TRANSPORT_STOP

        yield self._env.process(
            self._walk(self._position, vehicle_allocation.pick_up_position)
        )

        self.logger.debug(
            "Arrived at public transport stop at %s at time %s.",
            vehicle_allocation.pick_up_position,
            self._env.now,
        )

    def _wait_for_transport(
        self, vehicle_allocation: VehicleAllocation
    ) -> Generator[Any, Any, None]:
        """Wait for public transport vehicle to arrive at stop."""
        self._state = UserState.WAITING_FOR_TRANSPORT

        # TODO: Logic for waiting for transport arrival

        raise NotImplementedError("Waiting for transport not implemented yet.")

        # self._assigned_vehicle_arrived.succeed()

    def _start_trip(
        self, vehicle_allocation: VehicleAllocation, wait_time: float
    ) -> Generator[Process | Timeout, Any, None]:
        vehicle = vehicle_allocation.vehicle
        route = vehicle_allocation.associated_transportation_alternative.route

        if isinstance(vehicle, RideHailingVehicle):
            # Mount vehicle as passenger
            self.state = UserState.IN_TRANSPORT
            self.mount_vehicle(vehicle)

            # Vehicle drives to destination
            yield self._env.process(self.ride_in_vehicle(vehicle, route))

            self.park_vehicle(vehicle)  # type: ignore #TODO: This should not be done by the user
            self.unmount_vehicle(vehicle)

        elif isinstance(vehicle, SharedVehicle):
            # For shared vehicles, user acts as driver
            self.state = UserState.IN_TRANSPORT
            self.mount_vehicle_as_driver(vehicle)

            # User drives vehicle to destination
            yield self._env.process(self.drive_vehicle(vehicle, route))

            self.park_vehicle(vehicle)
            self.unmount_vehicle_as_driver(vehicle)

        else:
            raise NotImplementedError(f"Vehicle type {type(vehicle)} not supported")

        self._arrived_at_destination.succeed()
        self.state = UserState.FULFILLED
        self.logger.debug("Trip completed.")

    def _move_to_pick_up_position(
        self, vehicle_assignment: VehicleAllocation
    ) -> Generator[Process, Any, None]:
        """Move to the pickup position.

        # TODO: Currently unused, because vehicles come to the user. Remove? Keep for public transport?
        """
        # Set current state
        self._state = UserState.MOVING_TO_PICK_UP

        yield self._env.process(
            self._walk(self._position, vehicle_assignment.pick_up_position)
        )

        # Trigger next event
        self._arrived_at_pick_up_position.succeed()
        self.logger.debug(
            "Arrived at pick up position %s at time %s.", self.position, self._env.now
        )

    def _walk(
        self, origin: GeodesicPosition, destination: GeodesicPosition
    ) -> Generator[Timeout, Any, None]:
        """Simulate walking from origin to destination."""
        distance = origin >> destination
        duration = distance / SimulationVelocityConverter.kmh_to_meters_per_minute(
            self._walking_speed_kmh
        )
        self.logger.debug(
            "Walking from %s to %s. Distance: %s meters, duration: %s seconds.",
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
        """Request vehicle allocation for the selected transportation alternative."""
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
    ) -> Generator[Timeout, Any, dict[TransportationAlternative, float]]:
        """
        Calculate choice probabilities using the configured choice model.

        Parameters
        ----------
        available_alternatives : TransportationAlternativeBrowser
            Available transportation alternatives.

        Returns
        -------
        dict[TransportationAlternative, float]
            Mapping of alternatives to their choice probabilities (sum to 1.0).
        """
        # Batching delay (for allocation synchronization) #TODO: Can we get rid of this?
        yield self._env.timeout(1)

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
        """Mount vehicle as driver."""
        vehicle.mount_driver(self)

    def drive_vehicle(
        self, vehicle: SharedVehicle, route: Route
    ) -> Generator[Process | Timeout, Any, float]:
        """Drive vehicle along route."""
        vehicle.start_driving()
        vehicle_soc_before_driving = vehicle.current_state_of_charge
        for route_segment in route.route_segments:
            yield self._env.process(vehicle.move(route_segment))

        vehicle_soc_after_driving = vehicle.current_state_of_charge
        user_energy_consumption = vehicle_soc_before_driving - vehicle_soc_after_driving
        vehicle.stop_driving()
        return user_energy_consumption

    def park_vehicle(self, vehicle: SharedVehicle) -> None:
        """Park vehicle."""
        vehicle.park()

    def unmount_vehicle_as_driver(self, vehicle: SharedVehicle) -> None:
        """Unmount vehicle as driver."""
        vehicle.unmount_driver()

    # TODO : Probably can get rid of this
    def identify_driver(self) -> str:
        """Identify driver."""
        return f"User {self.uid}"

    # --------------------------
    # PassengerInterface
    # --------------------------
    def mount_vehicle(self, vehicle: RideHailingVehicle) -> None:
        """Mount vehicle as passenger."""
        vehicle.mount_passenger(self)

    def unmount_vehicle(self, vehicle: RideHailingVehicle) -> None:
        """Unmount vehicle as passenger."""
        vehicle.unmount_passenger(self)

    def ride_in_vehicle(
        self, vehicle: RideHailingVehicle, route: Route
    ) -> Generator[Process | Timeout, Any, None]:
        """Ride in vehicle as passenger.

        TODO: user currently acts as driver, need to change that
        """
        vehicle.start_driving()

        for route_segment in route.route_segments:
            yield self._env.process(vehicle.move(route_segment))

        vehicle.stop_driving()

        return

    # TODO : Probably can get rid of this
    def identify_passenger(self) -> str:
        """Identify passenger."""
        return f"User {self.uid}"
