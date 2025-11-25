"""
Transaction data structure for the simulation.

Defines the Transaction NamedTuple used to represent a single transaction record.
"""

from typing import NamedTuple

from simulation.helper.configuration.enums import TransactionState, VehicleType
from simulation.helper.types import RegionId, SimId


class Transaction(NamedTuple):
    """
    Represents a single transaction record in the simulation.

    Attributes
    ----------
    vehicle_uid : SimId or None
        Unique identifier for the vehicle. If not available, set to None.
    origin : RegionId
        Region ID of the trip origin.
    destination : RegionId
        Region ID of the trip destination.
    time_start : float
        Simulation time when the trip started.
    time_end : float
        Simulation time when the trip ended.
    price : float
        Price paid for the trip.
    revenue : float
        Revenue earned from the trip for the operator.
    distance : float
        Distance traveled during the trip.
    duration : float
        Duration of the trip.
    state : TransactionState
        State of the transaction (e.g., "Fulfilled", "Missed").
    accepted_vehicle_types : frozenset of VehicleType
        Set of accepted vehicle types for the trip.
    selected_vehicle_type : VehicleType or None, optional
        Selected vehicle type for the trip. If not available, set to None.
    pick_up_time : float or None, optional
        Time spent picking up the passenger (if available).
    energy_consumption : float or None, optional
        Energy consumed during the trip (if available).
    selected_vehicle_EV : str or bool or None, optional
        Whether the selected vehicle is electric (if available).
    """

    vehicle_uid: SimId | None
    origin: RegionId
    destination: RegionId
    time_start: float
    time_end: float
    price: float
    revenue: float
    distance: float
    duration: float
    state: TransactionState
    accepted_vehicle_types: frozenset[VehicleType]
    selected_vehicle_type: VehicleType | None = None
    pick_up_time: float | None = None
    energy_consumption: float | None = None
    selected_vehicle_EV: str | bool | None = None
