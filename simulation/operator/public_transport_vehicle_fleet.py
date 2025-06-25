from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.vehicle.public_transit_bus import Bus

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.infrastructure.route import PublicTransitRoute
    from simulation.world.world import World


class PublicTransportVehicleFleet(VehicleFleet):
    __slots__ = ("_busses", "_config", "_unserved_passengers")

    def __init__(self, sim: SimulationContext, world: World) -> None:
        super().__init__(sim=sim, world=world)
        self._config = sim.config
        self._sim = sim
        self._busses = []

        self._tracking = (
            None  # defer loading to run process, otherwise circular dependency
        )
        self._unserved_passengers = 0

    # Add the bus
    def spawn_bus(self, route: PublicTransitRoute) -> Bus:
        init_position = GeodesicPosition(self._sim, *route.origin.getExactLocation())

        bus = Bus(
            sim=self._sim,
            route=route,
            position=init_position,
            fleet=self,
            use_learning_agent=False,
            vehicle_config=self._config.transit_vehicles[
                "Bus"
            ],  # TODO: This should not be hardcoded
        )

        # TODO: Why is this not in the vehicle constructor ?
        self._busses.append(bus)
        self._world.add_vehicle(bus)

        return bus

    def clean_up_bus(self, bus: Bus):  # noqa: ANN201
        yield bus._has_reached_terminal  # noqa: SLF001

        # TODO: Why is this not in the vehicle destructor?
        self._busses.remove(bus)
        self._world.remove_vehicle(bus)
        # Check this again, what happens when the trip time is over but there are still passengers in the bus?
        # TODO: unmount all remaining passengers - is there a need for this?
        self.logger.debug(
            "There are still %s passengers onboard the bus",
            len(bus._passengers),  # noqa: SLF001
        )
        self._unserved_passengers = len(bus._passengers)  # noqa: SLF001

    # Return current busses
    def get_busses(self) -> list[Bus]:
        return self._busses
