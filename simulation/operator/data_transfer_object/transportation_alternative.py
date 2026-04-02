"""
Data transfer object for transportation alternatives.

Represents a potential trip option with estimated properties.
"""

from dataclasses import dataclass

from simulation.infrastructure.route import Route
from simulation.operator.interface.operator_interface import OperatorInterface
from simulation.vehicle.vehicle import Vehicle


@dataclass(frozen=True, slots=True)
class TransportationAlternative:
    """
    Represents a potential transportation alternative.

    Parameters
    ----------
    vehicle : Vehicle
        The vehicle associated with this alternative.
    route : Route
        The route for this alternative.
    price : float
        The price of the trip.
    duration : float
        The estimated duration of the trip.
    distance : float
        The estimated distance of the trip.
    convenience : float
        The convenience score (lower is better).
    operator : OperatorInterface
        The operator providing this alternative.
    route_to_pickup : Route | None, optional
        The route to the pickup location, by default None.
    est_pickup_time : float | None, optional
        The estimated pickup time, by default None.
    """

    vehicle: Vehicle
    route: Route
    price: float
    duration: float
    distance: float
    convenience: float
    operator: OperatorInterface
    route_to_pickup: Route | None = None
    est_pickup_time: float | None = None

    def __str__(self) -> str:
        """Return a string representation of the transportation alternative."""
        pickup_info = ""
        if self.route_to_pickup:
            pickup_info = (
                f", Distance to pickup {self.route_to_pickup.distance}, "
                f"Pick up time {self.est_pickup_time}"
            )

        return (
            f"Vehicle {self.vehicle}, Price {self.price}, Duration {self.duration}, "
            f"Distance {self.distance}, Convenience {self.convenience}{pickup_info}"
        )

    def __repr__(self) -> str:
        """Return a string representation of the transportation alternative."""
        return self.__str__()
