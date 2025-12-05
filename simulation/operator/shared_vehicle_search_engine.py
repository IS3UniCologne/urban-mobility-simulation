from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

from simulation.operator.search_engine import SearchEngine

if TYPE_CHECKING:
    from simulation.operator.search_engine import SearchEngineDependencies
    from simulation.operator.vehicle_fleet import VehicleFleet
    from simulation.tasks.transport_task import TransportTask

from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)


class SharedVehicleSearchEngine(SearchEngine):  # noqa: D101
    __slots__ = ("_env", "_fleet", "_sim")

    def __init__(self, deps: SearchEngineDependencies) -> None:
        self._sim = deps.sim
        self._env = self._sim.env
        self._fleet: VehicleFleet = deps.operator.fleet
        self._operator = deps.operator

    def search_for_transportation_alternatives(
        self, transport_task: TransportTask
    ) -> TransportationAlternativeBrowser:
        """
        Spot all available vehicles to user
        :param vehicle_search_task:
        :return: Available Alternatives along with auxilary information regarding trip
        """  # noqa: D205, D400
        browser = TransportationAlternativeBrowser()

        hexagon_origin = transport_task.origin.get_region_id()

        parking_vehicles_in_region = self._fleet.parking_vehicles_in_region(
            hexagon_origin
        )
        # Sort vehicles by ID to ensure deterministic iteration order
        parking_vehicles_sorted = sorted(
            parking_vehicles_in_region, key=lambda v: v.uid
        )

        # TODO: Shouldn't we use the vehicles position instead of the task's origin?
        origin = transport_task.origin
        destination = transport_task.destination

        # Info about the route - if we distinguish between car/scooter and ks/bike routes, move to for loop
        # Calc Route
        route = Route(origin, destination)

        # Calc Distance
        distance = route.distance  # Euclidean Distance

        # Add all available cars to alternative browser
        for vehicle in parking_vehicles_sorted:
            # Calc Duration
            duration = distance / vehicle.velocity

            # Calc Price
            price = duration * vehicle.price_per_minute + vehicle.price_per_trip

            # Put together
            transportation_alternative = TransportationAlternative(
                vehicle=vehicle,
                route=route,
                price=price,
                duration=duration,
                distance=distance,
                convenience=vehicle.convenience,
                operator=self._operator,
            )

            if vehicle.energy_system.has_enough_energy(distance):
                browser.add_transportation_alternative(transportation_alternative)

        return browser
