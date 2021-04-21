from .agent import Agent
from ..operator.search_engine_interface import SearchEngineInterface
from ..tasks.transport_task import TransportTask
from ..tasks.vehicle_search_task import VehicleSearchTask
from enum import Enum

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
    def __init__(self, position, name, transport_task: TransportTask, vehicle_search_service: SearchEngineInterface):
        self._name = name
        self._position = position
        self._transport_task = transport_task # Objective of agent
        self._vehicle_search_service = vehicle_search_service

        self._state = UserState.INITIALIZED

    def search_for_vehicle(self):
        self._state = UserState.SEARCHING_VEHICLE

        search_task = VehicleSearchTask(self._position)

        available_vehicles = self._vehicle_search_service.search_for_vehicles(search_task)

    def __str__(self):
        return f'My Name is {self._name}'