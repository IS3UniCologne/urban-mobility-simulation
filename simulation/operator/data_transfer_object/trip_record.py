"""
Data transfer object for trip records.

This module provides the TripRecord class, representing completed trips.
"""

from dataclasses import dataclass

from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)


@dataclass(frozen=True, slots=True)
class TripRecord:
    """
    Represents a completed trip.

    Parameters
    ----------
    alternative : TransportationAlternative
        The transportation alternative that was chosen.
    actual_wait_time : float
        The actual waiting time experienced by the user.
    energy_consumed : float
        The actual energy consumed during the trip.
    """

    alternative: TransportationAlternative
    actual_wait_time: float
    energy_consumed: float
