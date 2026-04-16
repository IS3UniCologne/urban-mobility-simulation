"""Data transfer objects for the operator module."""

from simulation.operator.data_transfer_object.charging_session import ChargingSession
from simulation.operator.data_transfer_object.transport_request import TransportRequest
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.data_transfer_object.vehicle_allocation import (
    VehicleAllocation,
)

__all__ = [
    "ChargingSession",
    "TransportRequest",
    "TransportationAlternative",
    "TransportationAlternativeBrowser",
    "VehicleAllocation",
]
