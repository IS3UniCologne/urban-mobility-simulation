from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.mixed_shared_vehicle_fleet import MixedSharedVehicleFleet
    from simulation.tasks.transportation_search_task import TransportationSearchTask

from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.interface.search_engine_interface import SearchEngineInterface


class SharedVehicleSearchEngine(SearchEngineInterface):  # noqa: D101
    __slots__ = ("_env", "_fleet", "_sim")

    def __init__(self, sim: SimulationContext) -> None:
        self._sim = sim
        self._env = sim.env
        self._fleet: MixedSharedVehicleFleet = None

    def search_for_transportation_alternatives(
        self, vehicle_search_task: TransportationSearchTask
    ) -> TransportationAlternativeBrowser:
        """
        Spot all available vehicles to user
        :param vehicle_search_task:
        :return: Available Alternatives along with auxilary information regarding trip
        """  # noqa: D205, D400
        browser = TransportationAlternativeBrowser()

        hexagon_origin = vehicle_search_task.agent_position.get_region_id()

        parking_vehicles_in_region = self._fleet.parking_vehicles_in_region(
            hexagon_origin
        )
        # Sort vehicles by ID to ensure deterministic iteration order
        parking_vehicles_sorted = sorted(
            parking_vehicles_in_region, key=lambda v: v.uid
        )

        # TODO: Shouldn't we use the vehicles position instead of the task's origin?
        origin = vehicle_search_task.transport_task.origin
        destination = vehicle_search_task.transport_task.destination

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
                vehicle, route, price, duration, distance, vehicle.convenience
            )

            if vehicle.has_enough_state_of_charge(distance):
                browser.add_transportation_alternative(transportation_alternative)

        return browser
