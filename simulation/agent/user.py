from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np
import simpy

import simulation.world.world as world
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from simulation.vehicle.walking import Walking
from tracking.tracking_interface import TrackingInterface

from ..environment.geodesic_environment import GeodesicEnvironment
from ..environment.geodesic_position import GeodesicPosition
from ..environment.position import Position
from ..helper.configuration.configuration import Configuration
from ..infrastructure.route import PublicTransitRoute
from ..operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from ..operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from ..operator.data_transfer_object.transportation_alternative_ridehailing import (
    TransportationAlternativeRideHailing,
)
from ..operator.data_transfer_object.vehicle_allocation import VehicleAllocation
from ..operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)
from ..tasks.transport_task import TransportTask
from ..tasks.transportation_search_task import TransportationSearchTask
from ..vehicle.interfaces.driver_interface import DriverInterface
from ..vehicle.interfaces.passenger_interface import PassengerInterface
from ..vehicle.public_transit_vehicle import (
    PublicTransitVehicle,
    PublicTransitVehicleFull,
    PublicTransitVehicleState,
)
from ..vehicle.shared_bike import SharedBike
from ..vehicle.shared_car import SharedCar
from ..vehicle.shared_kick_scooter import SharedKickScooter
from ..vehicle.shared_scooter import SharedScooter
from ..vehicle.vehicle import Vehicle, VehicleState
from ..vehicle_choice_model.vehicle_choice_behavior_interface import (
    VehicleChoiceBehaviorInterface,
)
from ..world.population.PopulationFactory import PopulationType
from .agent import Agent

if TYPE_CHECKING:
    from ..vehicle.public_transit_bus import Bus


class UserState(Enum):
    INITIALIZED = 0
    SEARCHING_TRANSPORT_ALTERNATIVES = 1
    SELECTING_TRANSPORT_ALTERNATIVES = 2
    ALLOCATING_VEHICLE = 3
    MOVING_TO_PICK_UP_POS = 4
    WAITING_FOR_VEHICLE = 5
    DRIVING = 6
    PAYING = 7
    FULFILLED = 8
    CANCELLED = 9
    MISSED = 10
    # ride hailing specifics
    REFUSED = 11
    # transit user specifics
    IN_TRANSPORT = 101
    MOVING_TO_DESTINATION = 102  # walk after last transit stop


class User(Agent, DriverInterface, TrackingInterface):
    user_id = 0
    exposes = ["_position"]

    def __init__(
        self,
        fleet,
        position,
        transport_task: TransportTask,
        transportation_search_service: SearchEngineInterface,
        payment_service: PaymentInterface,
        vehicle_assignment_service: VehicleAllocationEngineInterface,
        vehicle_choice_behavior: VehicleChoiceBehaviorInterface,
        population_type: PopulationType,
        env: simpy.Environment,
    ):
        self._id = User.user_id  # User ID
        User.user_id += 1  # Increment User Id

        self._position = position  # Initial Position of Agent
        self._transport_task = transport_task  # Objective of generated agent
        self._fleet = fleet  # The target fleet of user

        # Operator Interfaces
        self._transportation_search_service = (
            transportation_search_service  # Register Transport Search Service
        )
        self._vehicle_assignment_service = (
            vehicle_assignment_service  # Register Vehicle Assignment Service
        )
        self._payment_service = payment_service  # Register Payment Service

        # Consumer Type of User
        self._population_type = population_type

        # Simpy Environment
        self._env = env  # Simulation Environment

        # Vehicle Choice Model
        self._vehicle_choice_behavior = vehicle_choice_behavior

        # Events
        self._transportation_alternatives_received = self._env.event()
        self._transportation_alternatives_selected = self._env.event()
        self._transportation_alternatives_not_found = self._env.event()
        self._vehicle_allocated = self._env.event()
        self._arrived_at_pick_up_position = self._env.event()
        self._assigned_vehicle_arrived = self._env.event()
        self._arrived_at_destination = self._env.event()
        self.process_finished = self._env.event()

        self._position_changed = self._env.event()

        # Initial State and Runtime
        self._state = UserState.INITIALIZED  # Initial State of agent
        logging.debug(
            "Initialized.", extra={"clazz": self.__class__.__name__, "oid": self._id}
        )

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    def position(self, position: Position):
        self._position = position

        self._position_changed.succeed(position)
        self._position_changed = self._env.event()

    @property
    def transport_task(self):
        return self._transport_task

    def run(self):
        """
        Life Cycle of User
        :return:
        """

        while self._state != UserState.FULFILLED and self._state != UserState.MISSED:
            start_ordering_time = self._env.now

            ## Retrieve available transportation alternatives
            available_transportation_alternatives = yield self._env.process(
                self.search_for_alternatives()
            )

            # Select Alternative
            selected_transportation_alternative = yield self._env.process(
                self.select_transportation_alternative(
                    available_transportation_alternatives
                )
            )

            # Withdraw Request since no vehicle is available matching my needs
            if not selected_transportation_alternative:
                yield self._env.process(self.withdraw_request())
                break

            if isinstance(selected_transportation_alternative.vehicle, Walking):
                logging.debug(
                    f"User {self.id} chooses to walk to destination",
                    extra={"clazz": self.__class__.__name__, "oid": self._id},
                )
                yield self._env.process(
                    self.walk(
                        self.position,
                        selected_transportation_alternative.route.destination,
                    )
                )

                logging.debug(
                    f"User {self.id} has reached walking destination",
                    extra={"clazz": self.__class__.__name__, "oid": self._id},
                )
            else:
                # Vehicle Found and allocated?
                vehicle_allocation = yield self._env.process(
                    self.allocate_vehicle(selected_transportation_alternative)
                )

                # If not allocated, retry.
                if not vehicle_allocation:
                    logging.debug(
                        " Vehicle allocation was not successful. Retrying with another vehicle.",
                        extra={"clazz": self.__class__.__name__, "oid": self._id},
                    )

                    # Reset Events (so far) and try again
                    self._transportation_alternatives_received = self._env.event()
                    self._transportation_alternatives_selected = self._env.event()
                    self._transportation_alternatives_not_found = self._env.event()
                    self._vehicle_allocated = self._env.event()

                    continue  # retry again until vehicle supply is depleted

            start_driving_time = self._env.now

            wait_time = start_driving_time - start_ordering_time

            self._transport_task.actual_wait_time = wait_time

            yield self._env.process(self.move_to_pick_up_position(vehicle_allocation))

            yield self._env.process(self.wait_for_vehicle(vehicle_allocation))

            yield self._env.process(self.start_driving(vehicle_allocation))

            self._payment_service.pay_for_fulfilled_transportation_task(
                self, self._transport_task, selected_transportation_alternative
            )

            yield self._env.process(self.stop())

    def search_for_alternatives(self):
        """
            User searches for available mobility alternatives using concrete instance of py:mod:`~operator.SearchEngineInterface`
        :return:
        """

        # Wait for next event
        yield self._env.timeout(1)  # Open App
        # TODO: https://github.com/IS3UniCologne/urban-mobility-simulation/issues/50
        self._waiting_time = 0
        # Update current state
        self._state = UserState.SEARCHING_TRANSPORT_ALTERNATIVES

        # Search for transportation alternatives
        search_task = TransportationSearchTask(
            self._position, self._transport_task, self._fleet
        )

        available_transportation_alternatives = (
            self._transportation_search_service.search_for_transportation_alternatives(
                search_task
            )
        )

        # Vehicle Choice (moved to World Add User Function)
        # distance = self._transport_task.origin >> self._transport_task.destination
        # tc = TripCharacteristics(distance)
        # viable_vehicle_modes = self._vehicle_choice_behavior.choose_vehicle(tc)

        # Load Config File
        config = Configuration.instance()

        # Filter Transportation Alternatives based on Mode Choice and Walking Distances
        filtered_list = []
        for (
            alternative
        ) in available_transportation_alternatives.transportation_alternatives:
            if (
                isinstance(alternative.vehicle, Walking)
                and self._transport_task.viable_vehicle_modes[
                    alternative.vehicle.__class__.__name__
                ]
            ):
                filtered_list.append(
                    (0, alternative.price, alternative.convenience, alternative)
                )
                continue
            distance_to_vehicle = self.position >> alternative.vehicle.position
            if self._transport_task.viable_vehicle_modes[
                alternative.vehicle.__class__.__name__
            ]:
                if (
                    isinstance(alternative.vehicle, SharedCar)
                    and distance_to_vehicle
                    < config.get_shared_vehicle_config(
                        alternative.vehicle.__class__.__name__
                    ).max_walking_distance
                ):  # See own paper
                    filtered_list.append(
                        (
                            distance_to_vehicle,
                            alternative.price,
                            alternative.convenience,
                            alternative,
                        )
                    )
                elif (
                    isinstance(alternative.vehicle, SharedKickScooter)
                    and distance_to_vehicle
                    < config.get_shared_vehicle_config(
                        alternative.vehicle.__class__.__name__
                    ).max_walking_distance
                ):  # See Reck
                    filtered_list.append(
                        (
                            distance_to_vehicle,
                            alternative.price,
                            alternative.convenience,
                            alternative,
                        )
                    )
                elif (
                    isinstance(alternative.vehicle, SharedScooter)
                    and distance_to_vehicle
                    < config.get_shared_vehicle_config(
                        alternative.vehicle.__class__.__name__
                    ).max_walking_distance
                ):  # See Nothing..
                    filtered_list.append(
                        (
                            distance_to_vehicle,
                            alternative.price,
                            alternative.convenience,
                            alternative,
                        )
                    )
                elif (
                    isinstance(alternative.vehicle, SharedBike)
                    and distance_to_vehicle
                    < config.get_shared_vehicle_config(
                        alternative.vehicle.__class__.__name__
                    ).max_walking_distance
                ):  # See Nothing..
                    filtered_list.append(
                        (
                            distance_to_vehicle,
                            alternative.price,
                            alternative.convenience,
                            alternative,
                        )
                    )

        # Determine Vehicle Preference based on Population Type
        # a) Price Sensitive Users will prefer cheapest option
        # b) Convenience/Sustainable Users prefer slightly more expensive option
        if self._population_type == PopulationType.PRICE_SENSITIVE:
            # Sort Vehicle List by Price and Vicinity (Customer is rational and prefers the cheapest mode
            # and the closest vehicle, i.e., shortest walking distance)
            # vehicle[1] price, vehicle[0] distance to vehicle
            filtered_list.sort(key=lambda vehicle: (vehicle[1], vehicle[0]))
        elif self._population_type == PopulationType.CONVENIENCE_SEEKER:
            # Sort based on Convenience Score => The lower the score, the better
            # KS = 1, Scooter = 2, Car = 3 (could also be regarded as a sustainability score)
            filtered_list.sort(key=lambda vehicle: (vehicle[2], vehicle[0]))

        if filtered_list:
            distance, price, convenience, filtered_list = zip(*filtered_list)
            filtered_list = list(filtered_list)

        # Only Consider Alternatives matching Customer needs
        available_transportation_alternatives.transportation_alternatives = (
            filtered_list
        )
        self._waiting_time += 1
        # Trigger next event
        self._transportation_alternatives_received.succeed()
        logging.debug(
            f"Received transportation alternatives: {available_transportation_alternatives}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

        return available_transportation_alternatives

    def select_transportation_alternative(
        self, available_transportation_alternatives: TransportationAlternativeBrowser
    ) -> TransportationAlternative:
        """
            User selects transportation alternative
        :param available_transportation_alternatives:
        :return:
        """

        # Wait for event
        yield self._transportation_alternatives_received

        # Set current state
        self._state = UserState.SELECTING_TRANSPORT_ALTERNATIVES

        if len(available_transportation_alternatives.transportation_alternatives) == 0:
            # Trigger Missed Demand Event
            self._transportation_alternatives_not_found.succeed()

            return

        # Select first transportation alternative (transportation preferences are already in place see search_for_alt method)
        selected_transportation_alternative = (
            available_transportation_alternatives.transportation_alternatives[0]
        )

        # Trigger next event
        self._transportation_alternatives_selected.succeed(
            selected_transportation_alternative
        )
        logging.debug(
            f"Selected transportation alternative: {selected_transportation_alternative}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

        # selected_transportation_alternative.waiting_time = self._waiting_time
        return selected_transportation_alternative

    def allocate_vehicle(
        self, selected_transportation_alternative: TransportationAlternative
    ) -> VehicleAllocation:
        # Wait for event
        yield self._transportation_alternatives_selected

        # Set current state
        self._state = UserState.ALLOCATING_VEHICLE

        # Get Vehicle Allocation
        vehicle_allocation = yield self._env.process(
            self._vehicle_assignment_service.request_vehicle_allocation(
                self, selected_transportation_alternative
            )
        )

        self._vehicle_allocated.succeed()

        # Vehicle was successfully allocated to request
        if vehicle_allocation:
            # Trigger next event
            logging.debug(
                f"Vehicle {vehicle_allocation.vehicle.id} has been allocated to user {self._id}.",
                extra={"clazz": self.__class__.__name__, "oid": self._id},
            )

            # Return vehicle allocation
            return vehicle_allocation
        else:
            return None

    def move_to_pick_up_position(self, vehicle_assignment: VehicleAllocation):
        # Wait for event
        yield self._vehicle_allocated

        # Set current state
        self._state = UserState.MOVING_TO_PICK_UP_POS

        # Calculate route to pick up position, and update user's position
        yield self._env.process(
            self.walk(self._position, vehicle_assignment.pick_up_position)
        )

        # Trigger next event
        self._arrived_at_pick_up_position.succeed()
        logging.debug(
            f"Arrived at pick up position {self.position} at time {self._env.now}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def wait_for_vehicle(self, vehicle_assignment: VehicleAllocation):
        # Wait for event
        yield self._arrived_at_pick_up_position

        # Waiting time (after arrival)
        start_waiting = self._env.now

        # Update current state
        self._state = UserState.WAITING_FOR_VEHICLE

        # Notify operator that user is waiting at pick up position
        self._vehicle_assignment_service.notify_user_arrival_at_pick_up_position(
            vehicle_assignment
        )

        while self.position != vehicle_assignment.vehicle.position:
            yield vehicle_assignment.vehicle._position_changed

        # Trigger next event
        self._assigned_vehicle_arrived.succeed()
        logging.debug(
            f"Vehicle {vehicle_assignment.vehicle.id} has arrived after {self._env.now - start_waiting} time units at pick up position to pick up user {self._id}",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def start_driving(self, vehicle_allocation: VehicleAllocation):
        # Wait for event
        yield self._assigned_vehicle_arrived

        # Update current state
        self._state = UserState.DRIVING

        # Mount Vehicle and Start Driving
        self.mount_vehicle_as_driver(vehicle_allocation.vehicle)
        energy_consumed = yield self._env.process(
            self.drive_vehicle(
                vehicle_allocation.vehicle,
                vehicle_allocation.associated_transportation_alternative.route,
            )
        )
        self.park_vehicle(vehicle_allocation.vehicle)
        self.unmount_vehicle_as_driver(vehicle_allocation.vehicle)

        # Update Trip Information
        vehicle_allocation.associated_transportation_alternative.set_energy_consumed(
            energy_consumed
        )
        # Trigger next event
        self._arrived_at_destination.succeed()
        logging.debug(
            "Arrived at destination.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def stop(self):
        # Wait for next event
        yield self._arrived_at_destination

        # Update current state
        self._state = UserState.FULFILLED
        logging.debug(
            f"Transport request of user {self._id} has been successfully fulfilled.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def withdraw_request(self):
        """

        :param viable_vehicle_modes: User was willing to take either of the modes from this list
        :return:
        """
        # Wait for missed demand event
        yield self._transportation_alternatives_not_found

        # Update current state
        self._state = UserState.MISSED

        self._payment_service.withdraw_transportation_task(self, self._transport_task)

        logging.debug(
            f"Transport request of user {self._id} has been withdrawn due to lack of vehicles.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def walk(self, origin: GeodesicPosition, destination: GeodesicPosition):
        # duration = RoutePlanner.calculateDuration(user.position, vehicle_assignment.pick_up_position, Strategy.Walking)
        distance = origin >> destination
        duration = distance / 83.33  # 83.33 m/min (average agent speed = 5km/h)
        yield self._env.timeout(duration)
        self._position = destination

    """
        Implementation of DriverInterface to navigate the as driver mounted vehicle
    """

    def mount_vehicle_as_driver(self, vehicle):
        # Mount Vehicle
        vehicle.mount_driver(self)

    def drive_vehicle(self, vehicle, route):
        vehicle.start_driving()

        # State of Charge before driving
        vehicle_soc_before_driving = vehicle.current_state_of_charge

        for route_segment in route.route_segments:
            # distance = route_segment.distance
            # velocity = vehicle.velocity
            # time = distance / velocity

            # yield self._env.timeout(time)
            yield self._env.process(vehicle.move(route_segment))

        # State of Charge after driving
        vehicle_soc_after_driving = vehicle.current_state_of_charge

        # Consumed Energy (kWh)
        user_energy_consumption = vehicle_soc_before_driving - vehicle_soc_after_driving
        vehicle.stop_driving()

        # Return how much energy we consumed (and other factors if needed such as time)
        return user_energy_consumption

    def park_vehicle(self, vehicle):
        vehicle.park()

    def unmount_vehicle_as_driver(self, vehicle):
        vehicle.unmount_driver()

    def identify_driver(self):
        return f"User {self._id}"

    """
        Auxiliary Functions
    """

    @property
    def id(self):
        return self._id

    def __str__(self):
        return f"User with id {self._id} is in state {self._state} and has transportation task {self._transport_task}"

    def dump(self, exposed_only: bool = True) -> dict:
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            dump_attr = [
                "_transport_task",
                "_vehicle_choice_behavior",
                "_population_type",
                "_position",
                "_state",
            ]
            return {x: self.get(x) for x in dump_attr}


class TransitUser(User, PassengerInterface, TrackingInterface):
    exposes = ["transport_task"]
    transit_user_id = 0

    def __init__(
        self,
        position: GeodesicPosition,
        transport_task: TransportTask,
        transportation_search_service: SearchEngineInterface,
        payment_service: PaymentInterface,
        vehicle_assignment_service: VehicleAllocationEngineInterface,
        vehicle_choice_behavior: VehicleChoiceBehaviorInterface,
        population_type: PopulationType,
        env: simpy.Environment,
        passive=False,
    ):
        super(TransitUser, self).__init__(
            fleet=None,
            position=position,
            transport_task=transport_task,
            transportation_search_service=transportation_search_service,
            payment_service=payment_service,
            vehicle_assignment_service=vehicle_assignment_service,
            vehicle_choice_behavior=vehicle_choice_behavior,
            population_type=population_type,
            env=env,
        )
        self._id = TransitUser.transit_user_id  # User ID
        TransitUser.transit_user_id += 1  # Increment User Id

        # if the user is "passive", no vehicle allocation happens, rather the user opportunistically
        # boards transit that happens to move through the same hexagon. Another word for passive could be dumb.
        self._passive = passive

        # Config
        self._config = Configuration.instance()
        # TODO: somehow this must be decoupled - by making the user unaware of problems
        self._problem_config = self._config.dynamic_checkpoint_routing_config
        # Comment out for now to run a bus without RL Agent
        # self._bus_res = self._problem_config.action_resolution
        self._bus_res = 8

        # TODO: modify available_time over time
        self._available_time = (
            self._transport_task.max_wait_time
        )  # max available walk / wait time, can change by e.g. waiting

        # World / Environment Instance
        self._world = world.World.instance()
        self._geodesic_env = GeodesicEnvironment.getInstance()

        # Events
        self._arrived_at_last_stop = self._env.event()

    def run(self):
        """
        Life Cycle of TransitUser
        :return:
        """

        while self._state != UserState.FULFILLED and self._state != UserState.MISSED:
            try:
                if not self._passive:
                    # Retrieve available transportation alternatives
                    available_transportation_alternatives = yield self._env.process(
                        self.search_for_alternatives()
                    )

                    # Select Alternative
                    selected_transportation_alternative = yield self._env.process(
                        self.select_transportation_alternative(
                            available_transportation_alternatives
                        )
                    )

                    # Withdraw Request since no vehicle is available matching my needs
                    if not selected_transportation_alternative:
                        yield self._env.process(self.withdraw_request())
                        break

                    # Vehicle Found and allocated?
                    vehicle_allocation = yield self._env.process(
                        self.allocate_vehicle(selected_transportation_alternative)
                    )

                    # If not allocated, retry.
                    if not vehicle_allocation:
                        logging.debug(
                            " Vehicle allocation was not successful. Retrying with another vehicle.",
                            extra={"clazz": self.__class__.__name__, "oid": self._id},
                        )

                        # Reset Events (so far) and try again
                        self._transportation_alternatives_received = self._env.event()
                        self._transportation_alternatives_selected = self._env.event()
                        self._transportation_alternatives_not_found = self._env.event()
                        self._vehicle_allocated = self._env.event()

                        continue  # retry again until vehicle supply is depleted

                    yield self._env.process(
                        self.move_to_pick_up_position(vehicle_allocation)
                    )

                    yield self._env.process(self.wait_for_vehicle(vehicle_allocation))

                    yield self._env.process(self.start_transit(vehicle_allocation))

                    yield self._env.process((self.move_to_destination()))

                    self._payment_service.pay_for_fulfilled_transportation_task(
                        self, self._transport_task, selected_transportation_alternative
                    )
                else:
                    # TODO: even this opportunistic user should just walk in certain scenarios and withdraw its demand

                    # wait for some transit to spawn
                    if not self._world.vehicles:
                        yield self._env.timeout(1)
                        continue

                    vehicle = self._world.vehicles[
                        0
                    ]  # in this case, only one bus exists TODO: generalize?
                    # just wait for forever to be picked up hopefully

                    if not self._demand_aligns(vehicle):
                        self._state = UserState.MISSED
                        # self._payment_service.withdraw_transportation_task(self, self._transport_task)
                        logging.debug(
                            f"User demand is not aligned with routing corridor of bus {vehicle.id}, ",
                            extra={"clazz": self.__class__.__name__, "oid": self._id},
                        )
                        break
                    else:
                        yield self._env.process(self.wait_for_transit(vehicle))
                        # TODO: here we hardcode the runtime for problems, not nice
                        # yield self._env.process(self.start_passive_transit(vehicle))
                        yield self._env.process(
                            self.start_passive_checkpoint_transit(vehicle)
                        )
                        yield self._env.process((self.move_to_destination()))
                        selected_alternative = TransportationAlternative(
                            vehicle,
                            PublicTransitRoute(
                                self._transport_task.origin,
                                self._transport_task.destination,
                                vehicle.route._id,
                                vehicle.route.trip_id,
                            ),
                            price=0,
                            duration=np.inf,
                            distance=self._transport_task.origin
                            >> self._transport_task.destination,
                            convenience=0,  # TODO: only a placeholder
                        )
                        self._payment_service._tracked_demands.add(
                            (
                                self._transport_task.origin.getExactLocation(
                                    geojson=True
                                ),
                                self._transport_task.destination.getExactLocation(
                                    geojson=True
                                ),
                                int(self._transport_task.time * 60000),
                                True,
                            )
                        )
                        self._payment_service.pay_for_fulfilled_transportation_task(
                            self, self._transport_task, selected_alternative
                        )

                yield self._env.process(self.stop())

            except (simpy.Interrupt, PublicTransitVehicleFull) as e:
                novehicle = False
                if self._state == UserState.MOVING_TO_DESTINATION:
                    # user is interrupted on his way from last stop to final destination, count as fulfilled
                    # it is already counted towards the agents reward so it must be represented in service level as well
                    try:
                        self._state = UserState.FULFILLED
                        selected_alternative = TransportationAlternative(
                            vehicle,
                            PublicTransitRoute(
                                self._transport_task.origin,
                                self._transport_task.destination,
                                vehicle.route._id,
                                vehicle.route.trip_id,
                            ),
                            price=0,
                            duration=numpy.inf,
                            distance=self._transport_task.origin
                            >> self._transport_task.destination,
                            convenience=0,  # TODO: only a placeholder
                        )
                        self._payment_service._tracked_demands.add(
                            (
                                self._transport_task.origin.getExactLocation(
                                    geojson=True
                                ),
                                self._transport_task.destination.getExactLocation(
                                    geojson=True
                                ),
                                int(self._transport_task.time * 60000),
                                True,
                            )
                        )
                        self._payment_service.pay_for_fulfilled_transportation_task(
                            self, self._transport_task, selected_alternative
                        )
                    except NameError:
                        # vehicle was not assigned
                        novehicle = True
                if self._state != UserState.MOVING_TO_DESTINATION or novehicle:
                    self._state = UserState.MISSED
                    self._payment_service._tracked_demands.add(
                        (
                            self._transport_task.origin.getExactLocation(geojson=True),
                            self._transport_task.destination.getExactLocation(
                                geojson=True
                            ),
                            int(self._transport_task.time * 60000),
                            False,
                        )
                    )
                    self._payment_service.withdraw_transportation_task(
                        self, self._transport_task
                    )
                    if isinstance(e, simpy.Interrupt):
                        # can also be interrupt from vehicle full
                        logging.debug(
                            "User was not serviced before bus reached terminal destination.",
                            extra={"clazz": self.__class__.__name__, "oid": self._id},
                        )
                    elif isinstance(e, PublicTransitVehicleFull):
                        logging.debug(
                            "User was not able to board vehicle, vehicle is full.",
                            extra={"clazz": self.__class__.__name__, "oid": self._id},
                        )

        self.process_finished.succeed()

    def search_for_alternatives(self):
        # Update current state
        self._state = UserState.SEARCHING_TRANSPORT_ALTERNATIVES

        self._world.changed.succeed()
        self._world.changed = self._env.event()

        yield self._env.timeout(
            0.01
        )  # TODO: this is just hacking around the expected generator, opening app is instantaneous

        # Search for transportation alternatives
        search_task = TransportationSearchTask(
            self._position, self._transport_task, fleet=None
        )
        available_transportation_alternatives = (
            self._transportation_search_service.search_for_transportation_alternatives(
                search_task
            )
        )

        # use overall travel duration as sort criterion
        available_transportation_alternatives.transportation_alternatives.sort(
            key=lambda x: x.duration
        )

        # Trigger next event
        self._transportation_alternatives_received.succeed()
        logging.debug(
            f"Received transportation alternatives: {available_transportation_alternatives}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

        return available_transportation_alternatives

    def allocate_vehicle(
        self, selected_transportation_alternative: TransportationAlternative
    ) -> VehicleAllocation:
        # Wait for event
        yield self._transportation_alternatives_selected

        vehicle_allocation = yield self._env.process(
            self._vehicle_assignment_service.request_vehicle_allocation(
                self, selected_transportation_alternative
            )
        )
        self._vehicle_allocated.succeed()

        return vehicle_allocation

    def start_transit(self, vehicle_allocation: VehicleAllocation):
        # Wait for event
        yield self._assigned_vehicle_arrived

        # Update current state
        self._state = UserState.IN_TRANSPORT

        vehicle = vehicle_allocation.vehicle
        route = vehicle_allocation.associated_transportation_alternative.route

        self.mount_vehicle(vehicle)
        # drive in vehicle until stop closest to destination is reached
        while vehicle.current_stop != route.destination:
            yield vehicle._position_changed
        self.unmount_vehicle(vehicle)

        self._arrived_at_last_stop.succeed()

    def _demand_aligns(self, vehicle: Bus):
        if (
            self.transport_task.origin.get_hexagon(return_geom=False)
            == self.transport_task.destination.get_hexagon(return_geom=False)[0]
        ):
            # we don't want to service demands that board and unboard at the same station, they can walk
            return False

        # TODO: this is coupled deep with the DynamicRouting problem, too much hardcoded
        # incorridor = (
        # False
        # if not self._geodesic_env.filter_demands_by_area(
        #     [self.transport_task], self._problem_config.area
        # )
        # else True
        # )
        incorridor = True  # For now
        indirection = (
            False
            if not self._geodesic_env.filter_demands_by_direction(
                [self.transport_task], vehicle
            )
            else True
        )

        if not incorridor or not indirection:
            return False
        else:
            return True

    def start_passive_transit(self, vehicle: PublicTransitVehicle):
        # Wait for event
        yield self._assigned_vehicle_arrived

        if not vehicle.available_seats > 0:
            # Interrupt this user's process
            proc = self._world.user_process_by_id(self._id)["proc"]
            proc.interrupt()
            return
        else:
            # Update current state
            self._state = UserState.IN_TRANSPORT
            self.mount_vehicle(vehicle)

        # drive in vehicle until destination hexagon is reached, this might not happen at all
        while (
            self.transport_task.destination.get_hexagon(self._bus_res)[0]
            != vehicle.position.get_hexagon(self._bus_res)[0]
        ):
            yield vehicle._position_changed

        self.unmount_vehicle(vehicle)
        vehicle._dropoffs += 1

        self._arrived_at_last_stop.succeed()

    def start_passive_checkpoint_transit(self, vehicle: Bus):
        # TODO: checkpoint logic
        # when the checkpoint problem is running, we need to unmount at a checkpoint
        # if the destination was "passed" already, meaning if it is not reachable anymore
        # remember: the bus only moves forward toward the next checkpoint
        # Wait for event
        yield self._assigned_vehicle_arrived

        if not vehicle.available_seats > 0:
            # Interrupt this user's process
            proc = self._world.user_process_by_id(self._id)["proc"]
            proc.interrupt()
            return
        else:
            # Update current state
            self._state = UserState.IN_TRANSPORT
            self.mount_vehicle(vehicle)
            vehicle._pickups += 1

        while True:
            yield vehicle._position_changed

            # drive in vehicle while
            # a) destination not reached
            # b) checkpoint not reached that is "beyond" the destination
            at_dest = (
                self.transport_task.destination.get_hexagon(self._bus_res)[0]
                == vehicle.position.get_hexagon(self._bus_res)[0]
            )
            at_checkpoint = vehicle.state is PublicTransitVehicleState.AT_STOP
            unreachable_dest = False

            # if at_checkpoint:
            # check if the direction toward the passengers destination is aligned with the movement
            # direction of the bus
            # direction_bus = self._problem_config.direction
            # Set to none manually for now to not use the RL Agent configuration
            # direction_bus = None
            # direction_dest = self._geodesic_env.get_bearing(
            #      *vehicle.position.getExactLocation(),
            #      *self.transport_task.destination.getExactLocation(),
            # )
            # Cannot calculate unreachable destionation without the correct direction of the bus without the RL Agent
            # unreachable_dest = not self._geodesic_env.direction_aligns(
            #    direction_dest, direction_bus
            # )

            if (unreachable_dest and at_checkpoint) or at_dest:
                self.unmount_vehicle(vehicle)
                vehicle._dropoffs += 1
                self._arrived_at_last_stop.succeed()
                break

    def move_to_destination(self):
        # Wait for event
        yield self._arrived_at_last_stop

        # Update current state
        self._state = UserState.MOVING_TO_DESTINATION

        # walk to final destination
        try:
            yield self._env.process(
                self.walk(self._position, self._transport_task.destination)
            )
        except simpy.Interrupt:
            # user process should handle this
            return

        # Trigger next event
        self._arrived_at_destination.succeed()

    def wait_for_transit(self, vehicle: Vehicle):
        # wait indefinitely for transit pick up
        while (
            self.position.get_hexagon(self._bus_res)[0]
            != vehicle.position.get_hexagon(self._bus_res)[0]
        ):
            yield vehicle._position_changed

        self._assigned_vehicle_arrived.succeed()

    def mount_vehicle(self, vehicle):
        vehicle.mount_passenger(self)

    def unmount_vehicle(self, vehicle):
        vehicle.unmount_passenger(self)

    def identify_passenger(self):
        return f"TransitUser {self._id}"

    @property
    def available_time(self):
        return self._available_time

    def dump(self, exposed_only: bool = True) -> dict:
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            dump_attr = [
                "transport_task",
                "_vehicle_choice_behavior",
                "_population_type",
                "_position",
                "_passive",
            ]
            return {x: self.get(x) for x in dump_attr}

    def __str__(self):
        return f"TransitUser with id {self._id} is in state {self._state} and has transportation task {self._transport_task}"


class RideHailingUser(Agent, DriverInterface):
    user_id = 0

    def __init__(
        self,
        fleet,
        position,
        transport_task: TransportTask,
        transportation_search_service: SearchEngineInterface,
        payment_service: PaymentInterface,
        vehicle_assignment_service: VehicleAllocationEngineInterface,
        vehicle_choice_behavior: VehicleChoiceBehaviorInterface,
        population_type: PopulationType,
        env: simpy.Environment,
    ):
        self._id = RideHailingUser.user_id  # User ID
        RideHailingUser.user_id += 1  # Increment User Id

        self._position = position  # Initial Position of Agent
        self._transport_task = transport_task  # Objective of generated agent
        self._fleet = fleet  # The target fleet of user

        # Operator Interfaces
        self._transportation_search_service = (
            transportation_search_service  # Register Transport Search Service
        )
        self._vehicle_assignment_service = (
            vehicle_assignment_service  # Register Vehicle Assignment Service
        )
        self._payment_service = payment_service  # Register Payment Service

        # Consumer Type of User
        self._population_type = population_type

        # Simpy Environment
        self._env = env  # Simulation Environment

        # Vehicle Choice Model
        self._vehicle_choice_behavior = vehicle_choice_behavior
        # # use it if you want to consider deterministic coefficients
        # self._mode_choice_coefficients = Configuration.instance().MoD_coefficients[population_type.value]

        # # use it if you want to consider a random coefficient between the lower and the upper bounds
        self._mode_choice_coefficients = (
            Configuration.instance().generate_mode_choice_coefficient(
                population_type.value
            )
        )
        # # use it if you want to consider deterministic trust values
        # self._AV_truster = Configuration.instance().AV_trust[population_type.value]
        self._AV_truster = Configuration.instance().generate_AV_trust(
            population_type.value
        )

        # Events
        self._transportation_alternatives_received = self._env.event()
        self._transportation_alternatives_selected = self._env.event()
        self._transportation_alternatives_not_found = self._env.event()
        self._transportation_alternatives_refused = self._env.event()
        self._vehicle_allocated = self._env.event()
        self._arrived_at_pick_up_position = self._env.event()
        self._assigned_vehicle_arrived = self._env.event()
        self._arrived_at_destination = self._env.event()

        self.process_finished = self._env.event()
        self._position_changed = self._env.event()

        # Initial State and Runtime
        self._state = UserState.INITIALIZED  # Initial State of agent
        logging.debug(
            "Initialized.", extra={"clazz": self.__class__.__name__, "oid": self._id}
        )

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    def position(self, position: Position):
        self._position = position

        self._position_changed.succeed(position)
        self._position_changed = self._env.event()

    @property
    def transport_task(self):
        return self._transport_task

    def run(self):
        """
        Life Cycle of User
        :return:
        """
        while self._state != UserState.FULFILLED and self._state != UserState.MISSED:
            ### TODO: Define a probability rejection instead of a strict waiting_threshold
            ## Retrieve available transportation alternatives
            available_transportation_alternatives = yield self._env.process(
                self.search_for_alternatives()
            )
            # Always complete the list
            # available_transportation_alternatives = self.\
            #     complete_available_transportation_alternatives(available_transportation_alternatives)
            # Select Alternative
            selected_transportation_alternative = yield self._env.process(
                self.select_transportation_alternative(
                    available_transportation_alternatives
                )
            )
            # Withdraw Request since no vehicle is available matching my needs
            if not selected_transportation_alternative:
                yield self._env.process(self.withdraw_request())
                break

            # Vehicle Found and allocated?
            vehicle_allocation = yield self._env.process(
                self.allocate_vehicle(selected_transportation_alternative)
            )
            # If not allocated, retry.
            if not vehicle_allocation:
                logging.debug(
                    " Vehicle allocation was not successful. Retrying with another vehicle.",
                    extra={"clazz": self.__class__.__name__, "oid": self._id},
                )

                # Reset Events (so far) and try again
                self._transportation_alternatives_received = self._env.event()
                self._transportation_alternatives_selected = self._env.event()
                self._transportation_alternatives_refused = self._env.event()
                self._transportation_alternatives_not_found = self._env.event()
                self._vehicle_allocated = self._env.event()

                continue  # retry again until vehicle supply is depleted
            # We do not yield the following process again
            self._env.process(self.wait_for_vehicle(vehicle_allocation))
            yield self._env.process(
                vehicle_allocation.vehicle.move_to_pick_up_position(vehicle_allocation)
            )
            yield self._env.process(self.start_driving(vehicle_allocation))
            self._payment_service.pay_for_fulfilled_transportation_task(
                self, self._transport_task, selected_transportation_alternative
            )

            yield self._env.process(self.stop())

    def search_for_alternatives(self):
        """
            User searches for available mobility alternatives using concrete instance of py:mod:`~operator.SearchEngineInterface`
        :return:
        """
        self._waiting_time = 0
        while True:
            # Wait for next event
            yield self._env.timeout(1)  # Open App

            # Update current state
            self._state = UserState.SEARCHING_TRANSPORT_ALTERNATIVES

            # Search for transportation alternatives
            search_task = TransportationSearchTask(
                self._position, self._transport_task, self._fleet
            )

            available_transportation_alternatives = self._transportation_search_service.search_for_transportation_alternatives(
                search_task
            )

            # Filter Transportation Alternatives based on Mode Choice
            filtered_list = []
            for (
                alternative
            ) in available_transportation_alternatives.transportation_alternatives:
                filtered_list.append(
                    (
                        alternative.pick_up_time,
                        alternative.price,
                        alternative.convenience,
                        alternative.environment,
                        alternative.autonomous_vehicle,
                        alternative,
                    )
                )
            # Here we only determine two transportation alternatives (one AV and one HV)
            final_filtered_list = []
            autonomous_filtered_list = [alt for alt in filtered_list if alt[4] == 1]
            human_driven_filtered_list = [alt for alt in filtered_list if alt[4] == 0]
            if len(autonomous_filtered_list) > 0:
                closest_AV = sorted(autonomous_filtered_list, key=lambda alt: alt[0])[0]
                final_filtered_list.append(closest_AV)
            if len(human_driven_filtered_list) > 0:
                closest_HV = sorted(human_driven_filtered_list, key=lambda alt: alt[0])[
                    0
                ]
                final_filtered_list.append(closest_HV)

            if final_filtered_list:
                (
                    distance,
                    price,
                    convenience_ranking,
                    environment_ranking,
                    technology_skeptical_ranking,
                    final_filtered_list,
                ) = zip(*final_filtered_list)
                filtered_list = list(final_filtered_list)

            # Only Consider Alternatives matching Customer needs
            available_transportation_alternatives.transportation_alternatives = (
                filtered_list
            )

            # Trigger next event

            logging.debug(
                f"Received transportation alternatives: {available_transportation_alternatives}.",
                extra={"clazz": self.__class__.__name__, "oid": self._id},
            )
            # Break the loop if there is an available vehicle for the user
            self._waiting_time += 1

            if (
                len(available_transportation_alternatives.transportation_alternatives)
                >= 1
            ):
                self._transportation_alternatives_received.succeed()
                return available_transportation_alternatives

            if self._waiting_time > 5:
                break
        self._transportation_alternatives_received.succeed()
        return available_transportation_alternatives

    def complete_available_transportation_alternatives(self, alternatives):
        """
        This function ensures that there are always either two alternatives or zero
        :return:
        """

        if len(alternatives) == 1:
            alternative = alternatives[0]
            # mutual_alternative = alternative.copy()
            if alternative.vehicle_type == "AutonomousCar":
                pass

        return alternatives

    def transportation_alternative_utility_function(
        self, alternative: TransportationAlternativeRideHailing
    ):
        """
            This is a mode choice utility function for each alternative
        :param a transportation alternative:
        :return: a single scalar utility
        """
        coefficients = self._mode_choice_coefficients
        independent_variables = np.array(
            [
                1,
                alternative.price,
                alternative.waiting_time,
                alternative.electric_vehicle,
                alternative.duration,
                alternative.autonomous_vehicle,
                (1 - alternative.autonomous_vehicle),
                alternative.autonomous_vehicle * self._AV_truster,
                (1 - alternative.autonomous_vehicle) * self._AV_truster,
            ]
        )
        utility = np.dot(coefficients, independent_variables)
        return utility

    def get_utility_for_transportation_alternative(
        self, available_transportation_alternatives: TransportationAlternativeBrowser
    ):
        """
            Each user has different utilities for each alternative
        :param available_transportation_alternatives:
        :return: a dictionary of utilities
        """
        for (
            transportation_alternative
        ) in available_transportation_alternatives.transportation_alternatives:
            transportation_alternative._utility = (
                self.transportation_alternative_utility_function(
                    transportation_alternative
                )
            )

    def select_transportation_alternative(
        self, available_transportation_alternatives: TransportationAlternativeBrowser
    ) -> TransportationAlternativeRideHailing:
        """
            User selects transportation alternative
        :param available_transportation_alternatives:
        :return: a selected transportation alternative
        """

        # Wait for event
        yield self._transportation_alternatives_received

        # Set current state
        self._state = UserState.SELECTING_TRANSPORT_ALTERNATIVES

        if len(available_transportation_alternatives.transportation_alternatives) == 0:
            # Trigger Missed Demand Event

            self._transportation_alternatives_not_found.succeed()

            return
        self.get_utility_for_transportation_alternative(
            available_transportation_alternatives
        )
        utilities = np.append(
            np.array(
                [
                    alt.utility
                    for alt in available_transportation_alternatives.transportation_alternatives
                ]
            ),
            np.zeros(1),
        )

        # Here we consider the rejection of alternatives: if the utilities are lower than the based alternatives' utility

        # Calculate choice probabilities using the logit formula
        choice_probabilities = np.exp(utilities) / np.sum(np.exp(utilities))

        # Normalize choice probabilities
        normalized_probabilities = choice_probabilities / np.sum(choice_probabilities)

        # Choose the mode with the highest choice probability
        chosen_mode_index = np.argmax(normalized_probabilities)

        # if all(x < 10 for x in utilities):
        if chosen_mode_index == len(utilities) - 1:
            # self._transportation_alternatives_not_found.succeed()
            self._transportation_alternatives_refused.succeed()
            return
        else:
            selected_transportation_alternative = (
                available_transportation_alternatives.transportation_alternatives[
                    chosen_mode_index
                ]
            )
        # TODO: use logit model

        # sorted_alternative_based_on_utility = \
        #     sorted(available_transportation_alternatives.transportation_alternatives,
        #            key=lambda alternative: alternative.utility)
        #
        # selected_transportation_alternative = sorted_alternative_based_on_utility[0]
        selected_transportation_alternative.vehicle._suggested = True

        # if self._population_type == PopulationType.TECHNOLOGICALLY_SKEPTICAL:
        #     if not available_transportation_alternatives.transportation_alternatives[0].technology_skeptical:
        #         return

        # Select first transportation alternative (transportation preferences are already in place see search_for_alt method)
        # selected_transportation_alternative = available_transportation_alternatives.transportation_alternatives[0]

        selected_transportation_alternative.set_waiting_time(self._waiting_time)
        # Trigger next event
        self._transportation_alternatives_selected.succeed(
            selected_transportation_alternative
        )
        logging.debug(
            f"Selected transportation alternative: {selected_transportation_alternative.vehicle.state}.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )
        return selected_transportation_alternative

    def allocate_vehicle(
        self, selected_transportation_alternative: TransportationAlternative
    ) -> VehicleAllocation:
        # Wait for event
        yield self._transportation_alternatives_selected

        # Set current state
        self._state = UserState.ALLOCATING_VEHICLE

        # if the selected vehicle is serving a user we need to wait until the service is over and then allocate it
        if selected_transportation_alternative.vehicle.state == VehicleState.DRIVING:
            yield selected_transportation_alternative.vehicle._driving_finished
        # Get Vehicle Allocation
        vehicle_allocation = yield self._env.process(
            self._vehicle_assignment_service.request_vehicle_allocation(
                self, selected_transportation_alternative
            )
        )
        self._vehicle_allocated.succeed()

        # Vehicle was successfully allocated to request
        if vehicle_allocation:
            # Trigger next event
            logging.debug(
                f"Vehicle {vehicle_allocation.vehicle.id} has been allocated to user {self._id}.",
                extra={"clazz": self.__class__.__name__, "oid": self._id},
            )

            # Return vehicle allocation
            return vehicle_allocation
        else:
            return None

    def wait_for_vehicle(self, vehicle_assignment: VehicleAllocation):
        # Wait for event
        # yield self._arrived_at_pick_up_position

        # Waiting time (after arrival)
        start_waiting = self._env.now

        # Update current state
        self._state = UserState.WAITING_FOR_VEHICLE

        # Notify operator that user is waiting at pick up position
        self._vehicle_assignment_service.notify_user_arrival_at_pick_up_position(
            vehicle_assignment
        )

        while self.position != vehicle_assignment.vehicle.position:
            yield vehicle_assignment.vehicle._arrived_at_pick_up_position
        # Trigger next event
        self._assigned_vehicle_arrived.succeed()
        logging.debug(
            f"Vehicle {vehicle_assignment.vehicle.id} has arrived after {self._env.now - start_waiting} time units at pick up position to pick up user {self._id}",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def start_driving(self, vehicle_allocation: VehicleAllocation):
        # Wait for event
        yield self._assigned_vehicle_arrived

        # Update current state
        self._state = UserState.DRIVING

        # Mount Vehicle and Start Driving
        self.mount_vehicle_as_driver(vehicle_allocation.vehicle)
        energy_consumed = yield self._env.process(
            self.drive_vehicle(
                vehicle_allocation.vehicle,
                vehicle_allocation.associated_transportation_alternative.route,
            )
        )
        self.park_vehicle(vehicle_allocation.vehicle)
        self.unmount_vehicle_as_driver(vehicle_allocation.vehicle)

        # Update Trip Information
        vehicle_allocation.associated_transportation_alternative.set_energy_consumed(
            energy_consumed
        )
        # Trigger next event
        self._arrived_at_destination.succeed()
        logging.debug(
            "Arrived at destination.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def stop(self):
        # Wait for next event
        yield self._arrived_at_destination

        # Update current state
        self._state = UserState.FULFILLED
        logging.debug(
            f"Transport request of user {self._id} has been successfully fulfilled.",
            extra={"clazz": self.__class__.__name__, "oid": self._id},
        )

    def withdraw_request(self):
        """

        :param viable_vehicle_modes: User was willing to take either of the modes from this list
        :return:
        """
        # Wait for missed demand event
        events = (
            yield self._transportation_alternatives_not_found
            | self._transportation_alternatives_refused
        )

        # Update current state
        if self._transportation_alternatives_not_found in events:
            self._state = UserState.MISSED

            self._payment_service.withdraw_transportation_task(
                self, self._transport_task, state="MISSED"
            )

            logging.debug(
                f"Transport request of user {self._id} has been withdrawn due to lack of vehicles.",
                extra={"clazz": self.__class__.__name__, "oid": self._id},
            )
        elif self._transportation_alternatives_refused:
            self._state = UserState.REFUSED

            self._payment_service.withdraw_transportation_task(
                self, self._transport_task, state="REFUSED"
            )

            logging.debug(
                f"Transport request of user {self._id} has been refused.",
                extra={"clazz": self.__class__.__name__, "oid": self._id},
            )

    def walk(self, origin: GeodesicPosition, destination: GeodesicPosition):
        # duration = RoutePlanner.calculateDuration(user.position, vehicle_assignment.pick_up_position, Strategy.Walking)
        distance = origin >> destination
        duration = distance / 83.33  # 83.33 m/min (average agent speed = 5km/h)
        yield self._env.timeout(duration)
        self._position = destination

    """
        Implementation of DriverInterface to navigate the as driver mounted vehicle
    """

    def mount_vehicle_as_driver(self, vehicle):
        # Mount Vehicle
        vehicle.mount_driver(self)

    def drive_vehicle(self, vehicle, route):
        vehicle.start_driving()

        # State of Charge before driving
        vehicle_soc_before_driving = vehicle.current_state_of_charge

        for route_segment in route.route_segments:
            # distance = route_segment.distance
            # velocity = vehicle.velocity
            # time = distance / velocity

            # yield self._env.timeout(time)
            yield self._env.process(vehicle.move(route_segment))

        # State of Charge after driving
        vehicle_soc_after_driving = vehicle.current_state_of_charge

        # Consumed Energy (kWh)
        user_energy_consumption = vehicle_soc_before_driving - vehicle_soc_after_driving
        vehicle.stop_driving()

        # Return how much energy we consumed (and other factors if needed such as time)
        return user_energy_consumption

    def park_vehicle(self, vehicle):
        vehicle.park()

    def unmount_vehicle_as_driver(self, vehicle):
        vehicle.unmount_driver()

    def identify_driver(self):
        return f"User {self._id}"

    """
        Auxiliary Functions
    """

    @property
    def id(self):
        return self._id

    def __str__(self):
        return f"User with id {self._id} is in state {self._state} and has transportation task {self._transport_task}"
