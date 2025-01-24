import logging

from simpy import Environment

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.infrastructure.route import PublicTransitRoute
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.vehicle.public_transit_bus import Bus
from simulation.world.world import World
from tracking.tracking import Tracking


class PublicTransportVehicleFleet(VehicleFleet):
    def __init__(self, env: Environment):
        super(PublicTransportVehicleFleet, self).__init__(env)
        self._env = env
        self._config = Configuration.instance()
        self._busses = []
        self._world = (
            None  # defer loading to run process, otherwise circular dependency
        )
        self._bus_velocity = self._config.bus_config.velocity

        self._tracking = (
            None  # defer loading to run process, otherwise circular dependency
        )

        self._tracking = Tracking.instance()

    def get_available_vehicles(self, region):
        pass

    def vehicles_in_region(self, region: str):
        pass

    # Add the bus
    def spawn_bus(self, route: PublicTransitRoute):
        init_position = GeodesicPosition(*route.origin.getExactLocation())
        self._world = World.instance()

        bus = Bus(
            env=self._env,
            route=route,
            position=init_position,
            use_learning_agent=False,
            velocity=self._bus_velocity,
        )

        self._busses.append(bus)
        self._world.add_vehicle(bus)

        self._tracking.register(bus)

        return bus

    def clean_up_bus(self, bus: Bus):
        yield bus._has_reached_terminal

        self._busses.remove(bus)
        self._world.remove_vehicle(bus)
        self._tracking.unregister_by_obj(bus)

        # Check this again, what happens when the trip time is over but there are still passengers in the bus?
        # TODO: unmount all remaining passengers - is there a need for this?
        logging.debug(
            f"There are still {str(len(bus._seats))} passengers onboard the bus",
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )
        self._unserved_passengers = len(bus._seats)

    # Return current busses
    def get_busses(self):
        return self._busses
