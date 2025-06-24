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
    __slots__ = (
        "_bus_velocity",
        "_busses",
        "_config",
        "_unserved_passengers",
        "_world",
    )

    def __init__(self, env: Environment):  # noqa: ANN204
        super(PublicTransportVehicleFleet, self).__init__(env)  # noqa: UP008
        self._env = env
        self._config = Configuration()
        self._busses = []
        self._world = (
            None  # defer loading to run process, otherwise circular dependency
        )
        self._bus_velocity = self._config.transit_vehicles["Bus"].VELOCITY

        self._tracking = (
            None  # defer loading to run process, otherwise circular dependency
        )
        self._unserved_passengers = 0

        self._tracking = Tracking.instance()

    # Add the bus
    def spawn_bus(self, route: PublicTransitRoute):  # noqa: ANN201
        init_position = GeodesicPosition(*route.origin.getExactLocation())
        self._world = World.instance()

        bus = Bus(
            env=self._env,
            route=route,
            position=init_position,
            fleet=self,
            use_learning_agent=False,
            velocity=self._bus_velocity,
        )

        self._busses.append(bus)
        self._world.add_vehicle(bus)

        self._tracking.register(bus)

        return bus

    def clean_up_bus(self, bus: Bus):  # noqa: ANN201
        yield bus._has_reached_terminal  # noqa: SLF001

        self._busses.remove(bus)
        self._world.remove_vehicle(bus)
        self._tracking.unregister_by_obj(bus)

        # Check this again, what happens when the trip time is over but there are still passengers in the bus?
        # TODO: unmount all remaining passengers - is there a need for this?
        logging.debug(
            "There are still %s passengers onboard the bus",
            len(bus._passengers),  # noqa: SLF001
            extra={"clazz": self.__class__.__name__, "oid": ""},
        )
        self._unserved_passengers = len(bus._passengers)  # noqa: SLF001

    # Return current busses
    def get_busses(self):  # noqa: ANN201
        return self._busses
