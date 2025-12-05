"""Module for vehicle movement statistics.

These are returned after a vehicle completes a movement.
"""

from dataclasses import dataclass


@dataclass
class MovementStats:
    """Statistics for a vehicle movement.

    Attributes
    ----------
    energy_consumed : float
        The amount of energy consumed during the movement (kWh or Liters).
    distance_travelled : float
        The distance travelled during the movement (meters).
    time_taken : float
        The time taken for the movement (minutes).
    """

    energy_consumed: float
    distance_travelled: float
    time_taken: float
