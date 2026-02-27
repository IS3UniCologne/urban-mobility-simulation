"""Data transfer object for transport requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.enums import VehicleType
    from simulation.helper.types import SimTime


@dataclass(frozen=True, slots=True)
class TransportRequest:
    """DTO representing a user's transport request.

    Parameters
    ----------
    creation_time : SimTime
        The simulation time when this request was created.
    origin : GeodesicPosition
        The starting position of the transport request.
    destination : GeodesicPosition
        The target position of the transport request.
    accepted_vehicle_types : frozenset of VehicleType
        The vehicle types the user is willing to accept.
    """

    creation_time: SimTime
    origin: GeodesicPosition
    destination: GeodesicPosition
    accepted_vehicle_types: frozenset[VehicleType]
