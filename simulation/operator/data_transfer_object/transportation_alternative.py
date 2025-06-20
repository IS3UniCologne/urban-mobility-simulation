"""
Data transfer object for transportation alternatives.

Represents a potential trip option with estimated properties.
"""

from dataclasses import dataclass

from simulation.infrastructure.route import Route
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
    """

    vehicle: Vehicle
    route: Route
    price: float
    duration: float
    distance: float
    convenience: float

    def __str__(self) -> str:
        return (
            f"Vehicle {self.vehicle}, Price {self.price}, Duration {self.duration}, "
            f"Distance {self.distance}, Convenience {self.convenience}"
        )

    def __repr__(self) -> str:
        return self.__str__()
