from .agent import Agent
from ..environment.position import Position
from ..operator.data_transfer_object.transportation_alternative import TransportationAlternative
from ..operator.data_transfer_object.transportation_alternative_browser import TransportationAlternativeBrowser
from simulation.operator.interface.search_engine_interface import SearchEngineInterface
from ..operator.data_transfer_object.vehicle_allocation import VehicleAllocation
from ..operator.interface.payment_interface import PaymentInterface
from ..operator.interface.vehicle_allocation_engine_interface import VehicleAllocationEngineInterface
from ..tasks.transport_task import TransportTask
from ..tasks.transportation_search_task import TransportationSearchTask
from enum import Enum
import simpy

import logging

from ..vehicle.interfaces.driver_interface import DriverInterface
from ..vehicle.shared_car import SharedCar
from ..vehicle.shared_kick_scooter import SharedKickScooter
from ..vehicle.shared_scooter import SharedScooter
from ..vehicle_choice_model.trip_characteristics import TripCharacteristics
from ..vehicle_choice_model.vehicle_choice_behavior_interface import VehicleChoiceBehaviorInterface


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


class User(Agent, DriverInterface):
    user_id = 0

    def __init__(self, position, transport_task: TransportTask, transportation_search_service: SearchEngineInterface,
                 payment_service: PaymentInterface, vehicle_assignment_service: VehicleAllocationEngineInterface,
                 vehicle_choice_behavior: VehicleChoiceBehaviorInterface, env: simpy.Environment):
        self._id = User.user_id  # User ID
        User.user_id += 1  # Increment User Id

        self._position = position  # Initial Position of Agent
        self._transport_task = transport_task  # Objective of generated agent

        # Operator Interfaces
        self._transportation_search_service = transportation_search_service  # Register Transport Search Service
        self._vehicle_assignment_service = vehicle_assignment_service  # Register Vehicle Assignment Service
        self._payment_service = payment_service # Register Payment Service

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

        self._position_changed = self._env.event()

        # Initial State and Runtime
        self._state = UserState.INITIALIZED  # Initial State of agent
        logging.debug(f"Initialized.", extra={"clazz": self.__class__.__name__, "oid": self._id})

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    def position(self, position: Position):
        self._position = position

        self._position_changed.succeed(position)
        self._position_changed = self._env.event()


    def run(self):
        """
        Life Cycle of User
        :return:
        """

        while self._state != UserState.FULFILLED and self._state != UserState.MISSED:
            ## Retrieve available transportation alternatives
            available_transportation_alternatives = yield self._env.process(self.search_for_alternatives())

            # Select Alternative
            selected_transportation_alternative = yield self._env.process(
                self.select_transportation_alternative(available_transportation_alternatives))

            # Withdraw Request since no vehicle is available matching my needs
            if not selected_transportation_alternative:
                yield self._env.process(self.withdraw_request())
                break
                
            # Vehicle Found and allocated?
            vehicle_allocation = yield self._env.process(self.allocate_vehicle(selected_transportation_alternative))

            # If not allocated, retry.
            if not vehicle_allocation:
                logging.debug(f" Vehicle allocation was not successful. Retrying with another vehicle.",
                              extra={"clazz": self.__class__.__name__, "oid": self._id})

                # Reset Events (so far) and try again
                self._transportation_alternatives_received = self._env.event()
                self._transportation_alternatives_selected = self._env.event()
                self._transportation_alternatives_not_found = self._env.event()
                self._vehicle_allocated = self._env.event()

                continue # retry again until vehicle supply is depleted

            yield self._env.process(self.move_to_pick_up_position(vehicle_allocation))

            yield self._env.process(self.wait_for_vehicle(vehicle_allocation))

            yield self._env.process(self.start_driving(vehicle_allocation))

            self._payment_service.pay_for_fulfilled_transportation_task(self, self._transport_task, selected_transportation_alternative)

            yield self._env.process(self.stop())

    def search_for_alternatives(self):
        """
            User searches for available mobility alternatives using concrete instance of py:mod:`~operator.SearchEngineInterface`
        :return:
        """

        # Wait for next event
        yield self._env.timeout(1)  # Open App

        # Update current state
        self._state = UserState.SEARCHING_TRANSPORT_ALTERNATIVES

        # Search for transportation alternatives
        search_task = TransportationSearchTask(self._position, self._transport_task)

        available_transportation_alternatives = self._transportation_search_service.search_for_transportation_alternatives(
            search_task)

        # Vehicle Choice (moved to World Add User Function)
        # distance = self._transport_task.origin >> self._transport_task.destination
        # tc = TripCharacteristics(distance)
        # viable_vehicle_modes = self._vehicle_choice_behavior.choose_vehicle(tc)

        # TODO: We could move the walking distances to the config file, if needed.
        # Filter Transportation Alternatives based on Mode Choice and Walking Distances
        filtered_list = []
        for alternative in available_transportation_alternatives.transportation_alternatives:
            distance_to_vehicle = self.position >> alternative.vehicle.position
            if alternative.vehicle.__class__.__name__ in self._transport_task.viable_vehicle_modes:
                if isinstance(alternative.vehicle, SharedCar) and distance_to_vehicle < 500: # See own paper
                    filtered_list.append((distance_to_vehicle, alternative.price, alternative))
                elif isinstance(alternative.vehicle, SharedKickScooter) and distance_to_vehicle < 200: # See Reck
                    filtered_list.append((distance_to_vehicle, alternative.price, alternative))
                elif isinstance(alternative.vehicle, SharedScooter) and distance_to_vehicle < 350: # See Nothing..
                    filtered_list.append((distance_to_vehicle, alternative.price, alternative))

        # Sort Vehicle List by Price and Vicinity (Customer is rational and prefers the cheapest mode
        # and the closest vehicle, i.e., shortest walking distance)
        # vehicle[1] price, vehicle[0] distance to vehicle
        filtered_list.sort(key = lambda vehicle: (vehicle[1], vehicle[0]))

        if filtered_list:
            distance, price, filtered_list = zip(*filtered_list)
            filtered_list = list(filtered_list)

        # Only Consider Alternatives matching Customer needs
        available_transportation_alternatives.transportation_alternatives = filtered_list

        # Trigger next event
        self._transportation_alternatives_received.succeed()
        logging.debug(f"Received transportation alternatives: {available_transportation_alternatives}.",
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

        return available_transportation_alternatives

    def select_transportation_alternative(self,
                                          available_transportation_alternatives: TransportationAlternativeBrowser) -> TransportationAlternative:
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
        selected_transportation_alternative = available_transportation_alternatives.transportation_alternatives[0]

        # Trigger next event
        self._transportation_alternatives_selected.succeed(selected_transportation_alternative)
        logging.debug(f"Selected transportation alternative: {selected_transportation_alternative}.",
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

        return selected_transportation_alternative

    def allocate_vehicle(self, selected_transportation_alternative: TransportationAlternative) -> VehicleAllocation:
        # Wait for event
        yield self._transportation_alternatives_selected

        # Set current state
        self._state = UserState.ALLOCATING_VEHICLE

        # Get Vehicle Allocation
        vehicle_allocation = yield self._env.process(
            self._vehicle_assignment_service.request_vehicle_allocation(self, selected_transportation_alternative))

        self._vehicle_allocated.succeed()

        # Vehicle was successfully allocated to request
        if vehicle_allocation:
            # Trigger next event
            logging.debug(f"Vehicle {vehicle_allocation.vehicle.id} has been allocated to user {self._id}.",
                          extra={"clazz": self.__class__.__name__, "oid": self._id})

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
        # duration = RoutePlanner.calculateDuration(user.position, vehicle_assignment.pick_up_position, Strategy.Walking)
        distance = self.position >> vehicle_assignment.pick_up_position # Eucl. Distance
        duration = distance/83.33 # 83.33 m/min (average agent speed = 5km/h)

        yield self._env.timeout(duration)
        self.position = vehicle_assignment.pick_up_position

        # Trigger next event
        self._arrived_at_pick_up_position.succeed()
        logging.debug(f"Arrived at pick up position {self.position} at time {self._env.now}.",
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    def wait_for_vehicle(self, vehicle_assignment: VehicleAllocation):
        # Waiting time
        start_waiting = self._env.now

        # Wait for event
        yield self._arrived_at_pick_up_position

        # Update current state
        self._state = UserState.WAITING_FOR_VEHICLE

        # Notify operator that user is waiting at pick up position
        self._vehicle_assignment_service.notify_user_arrival_at_pick_up_position(vehicle_assignment)

        while self.position != vehicle_assignment.vehicle.position:
            vehicle_location = yield vehicle_assignment.vehicle._position_changed

        # Trigger next event
        self._assigned_vehicle_arrived.succeed()
        logging.debug(
            f"Vehicle {vehicle_assignment.vehicle.id} has arrived after {self._env.now - start_waiting} time units at pick up position to pick up user {self._id}",
            extra={"clazz": self.__class__.__name__, "oid": self._id})

    def start_driving(self, vehicle_allocation: VehicleAllocation):
        # Wait for event
        yield self._assigned_vehicle_arrived

        # Update current state
        self._state = UserState.DRIVING

        # Mount Vehicle and Start Driving
        self.mount_vehicle_as_driver(vehicle_allocation.vehicle)
        yield self._env.process(self.drive_vehicle(vehicle_allocation.vehicle, vehicle_allocation.associated_transportation_alternative.route))
        self.park_vehicle(vehicle_allocation.vehicle)
        self.unmount_vehicle_as_driver(vehicle_allocation.vehicle)

        # Trigger next event
        self._arrived_at_destination.succeed()
        logging.debug(f"Arrived at destination.", extra={"clazz": self.__class__.__name__, "oid": self._id})

    def stop(self):
        # Wait for next event
        yield self._arrived_at_destination

        # Update current state
        self._state = UserState.FULFILLED
        logging.debug(f"Transport request of user {self._id} has been successfully fulfilled.",
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

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

        logging.debug(f"Transport request of user {self._id} has been withdrawn due to lack of vehicles.",
                      extra={"clazz": self.__class__.__name__, "oid": self._id})

    """
        Implementation of DriverInterface to navigate the as driver mounted vehicle 
    """
    def mount_vehicle_as_driver(self, vehicle):
        # Mount Vehicle
        vehicle.mount_driver(self)

    def drive_vehicle(self, vehicle, route):
        vehicle.start_driving()

        for route_segment in route.route_segments:
            distance = route_segment.distance
            velocity = vehicle.velocity
            time = distance/velocity

            # yield self._env.timeout(time)
            yield self._env.process(vehicle.move(route_segment))

        vehicle.stop_driving()

    def park_vehicle(self, vehicle):
        vehicle.park()

    def unmount_vehicle_as_driver(self, vehicle):
        vehicle.unmount_driver()

    def identify_driver(self):
        return f'User {self._id}'

    """
        Auxiliary Functions  
    """
    @property
    def id(self):
        return self._id

    def __str__(self):
        return f'User with id {self._id} is in state {self._state} and has transportation task {self._transport_task}'
