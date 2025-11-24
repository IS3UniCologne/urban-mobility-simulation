from __future__ import annotations  # noqa: D100

from dataclasses import dataclass
from typing import TYPE_CHECKING

from simulation.environment.geodesic_position import GeodesicPosition

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition
    from simulation.helper.configuration.enums import VehicleType
    from simulation.helper.types import SimTime


@dataclass(frozen=True, slots=True)
class TransportTask:  # noqa: D101
    creation_time: SimTime
    origin: GeodesicPosition
    destination: GeodesicPosition
    accepted_vehicle_types: frozenset[VehicleType]
