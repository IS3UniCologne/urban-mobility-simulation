from .agent import Agent
from ..operator.search_engine_interface import SearchEngineInterface
from ..tasks.transport_task import TransportTask
from ..tasks.vehicle_search_task import VehicleSearchTask
from enum import Enum
import simpy

class UserState(Enum):
    INITIALIZED = 0
    SEARCHING_VEHICLE = 1
    SELECTING_VEHICLE = 2
    MOUNTING_VEHICLE  = 3
    DISMOUNTING_VEHICLE = 4
    DRIVING = 5
    PAYING = 6
    FINISHED = 7

class User(Agent):
    def __init__(self, position, name, transport_task: TransportTask, vehicle_search_service: SearchEngineInterface, env: simpy.Environment):
        self._name = name                                                       # Name of Agent (ID)
        self._position = position                                               # Initial Position of Agent
        self._transport_task = transport_task                                   # Objective of generated agent
        self._vehicle_search_service = vehicle_search_service                   # Register Vehicle Search Service
        self._env = env                                                         # Simulation Environment

        self._state = UserState.INITIALIZED                                     # Initial State of agent
        self._action = self._env.process(self.run())                            # Spawn agent

    def run(self):
        while self._state != UserState.FINISHED:
            available_vehicles = yield self._env.process(self.search_for_vehicle())

            print(self._env.now)

            yield self._env.process(self.select_available_vehicle())
            print(self._env.now)

            yield self._env.process(self.stop())

            print(self._env.now)

    def stop(self):
        self._state = UserState.FINISHED

        yield self._env.timeout(0)

    def search_for_vehicle(self):
        """
            User searches for available vehicles using concrete instance of py:mod:`~operator.SearchEngineInterface`
        :return:
        """
        self._state = UserState.SEARCHING_VEHICLE

        search_task = VehicleSearchTask(self._position)

        available_vehicles = self._vehicle_search_service.search_for_vehicles(search_task)
        available_vehicles = ['Huhu']

        yield self._env.timeout(1)
        return available_vehicles

    def select_available_vehicle(self):
        self._state = UserState.SELECTING_VEHICLE
        # Implement Choice Behavior
        yield self._env.timeout(5)


    def __str__(self):
        return f'My Name is {self._name}'