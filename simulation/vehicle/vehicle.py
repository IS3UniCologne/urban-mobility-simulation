from abc import ABC, abstractmethod
from simulation.agent.agent import Agent
from simulation.environment.position import Position


class Vehicle(ABC):

    def __init__(self, position, available_seats, max_available_seats):
        self._position = position
        self._available_seats = available_seats
        self._max_available_seats = max_available_seats
        self._seats = []

    # Properties
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        self._state = state

    @property
    def position(self) -> Position:
        return self._position

    @position.setter
    def position(self, position : Position):
        self._position = position

    @property
    def available_seats(self):
        return self._available_seats

    @available_seats.setter
    def available_seats(self, available_seats):
        self._available_seats = available_seats

    @property
    def max_available_seats(self):
        return self._max_available_seats

    @max_available_seats.setter
    def max_available_seats(self, max_available_seats):
        self._max_available_seats = max_available_seats


    # Methods
    @abstractmethod
    def start_driving(self):
        pass

    @abstractmethod
    def stop_driving(self):
        pass

    def mount(self, agent: Agent):
        if(len(self._seats) < self._available_seats):
            self._seats.append(agent)
            self._available_seats -= 1
        elif agent in self._seats:
            raise Exception('Agent is already in vehicle.')
        else:
            raise Exception('Vehicle is full.')

    def dismount(self, agent: Agent):
        if agent in self._seats:
            self._seats.remove(agent)
            self._available_seats += 1
        else:
            raise Exception('Agent is not in vehicle.')

    @abstractmethod
    def __str__(self):
        pass