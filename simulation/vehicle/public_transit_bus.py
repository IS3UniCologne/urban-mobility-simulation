from simpy import Environment

from simulation.vehicle.public_transit_vehicle import PublicTransitVehicle


class Bus(PublicTransitVehicle):

    def __init__(self, env: Environment, position, max_available_seats=100, velocity = 833.33):
        """

        :param env:
        :param position:
        :param max_available_seats: depends on type of bus - TODO: see SVG busses
        :param velocity: 16.67 m/min * 50 (city limit) - TODO: use road network speed limits?
        """
        super(Bus, self).__init__(env, position, max_available_seats, velocity)