"""
Transaction data structure for the simulation.

Defines the Transaction NamedTuple used to represent a single transaction record.
"""

from typing import NamedTuple


class Transaction(NamedTuple):
    """
    Represents a single transaction record in the simulation.

    Parameters
    ----------
    vehicle_id : int or None
        Unique identifier for the vehicle. If not available, set to None.
    origin : str
        Region ID of the trip origin.
    destination : str
        Region ID of the trip destination.
    time_start : float
        Simulation time when the trip started.
    time_end : float
        Simulation time when the trip ended.
    price : float
        Price paid for the trip.
    distance : float
        Distance traveled during the trip.
    duration : float
        Duration of the trip.
    selected_vehicle_mode : str
        Name of the selected vehicle mode.
    state : str
        State of the transaction (e.g., "Fulfilled", "Missed").
    viable_vehicle_modes : dict[str, int]
        Dictionary mapping vehicle mode names to 1 (available) or 0 (not available).
    wait_time : float or None, optional
        Waiting time before the trip started (if available).
    waiting_time : float or None, optional
        Duplicate (?) of wait_time (if available). TODO: Straighten this out #50
    pick_up_time : float or None, optional
        Time spent picking up the passenger (if available).
    energy_consumption : float or None, optional
        Energy consumed during the trip (if available).
    selected_vehicle_EV : str or bool or None, optional
        Whether the selected vehicle is electric (if available).
    """

    vehicle_id: int | None
    origin: str
    destination: str
    time_start: float
    time_end: float
    price: float
    distance: float
    duration: float
    selected_vehicle_mode: str
    state: str
    viable_vehicle_modes: dict[str, int]
    wait_time: float | None = None
    waiting_time: float | None = None
    pick_up_time: float | None = None
    energy_consumption: float | None = None
    selected_vehicle_EV: str | bool | None = None
