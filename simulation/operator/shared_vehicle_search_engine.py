"""Search engine for shared vehicle transportation alternatives."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.operator.search_engine import SearchEngine
from simulation.vehicle.shared_vehicle import SharedVehicle

if TYPE_CHECKING:
    from simulation.helper.enums import VehicleType
    from simulation.operator.data_transfer_object.transport_request import (
        TransportRequest,
    )
    from simulation.operator.search_engine import SearchEngineDependencies
    from simulation.operator.vehicle_fleet import VehicleFleet

from simulation.infrastructure.route import Route
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)


class SharedVehicleSearchEngine(SearchEngine):
    """
    Search engine for parked shared vehicles near the trip origin.

    Parameters
    ----------
    deps : SearchEngineDependencies
        Shared search engine dependencies.
    """

    __slots__ = ("_env", "_fleet", "_radii", "_sim")

    def __init__(self, deps: SearchEngineDependencies) -> None:
        self._sim = deps.sim
        self._env = self._sim.env
        self._fleet: VehicleFleet = deps.operator.fleet
        self._operator = deps.operator

        self._radii: dict[VehicleType, float | int] = {
            config.VEHICLE_TYPE: config.WALKING_DISTANCE
            for config in self._fleet.config.VEHICLES
            if config.WALKING_DISTANCE is not None
        }

    def search_for_transportation_alternatives(
        self, transport_task: TransportRequest
    ) -> TransportationAlternativeBrowser:
        """
        Spot all available vehicles to user.

        Parameters
        ----------
        transport_task : TransportRequest
            Transport demand to serve.

        Returns
        -------
        TransportationAlternativeBrowser
            Available alternatives with auxiliary trip information.
        """
        browser = TransportationAlternativeBrowser()

        parking_vehicles_in_region = self._fleet.parking_vehicles_in_radius(
            transport_task.origin, radius=self._radii
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
            if not isinstance(vehicle, SharedVehicle):
                continue

            # Calc Duration
            duration = vehicle.calculate_travel_time(distance)

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
