"""Helper types for the simulation package."""

from typing import NewType, TypeAlias

# SimPy defines this as float|int but float works fine for us.
SimTime: TypeAlias = float

# RegionId represents a unique identifier for a spatial region (e.g., an H3 hex ID).
RegionId = NewType("RegionId", str)
"""Spatial region identifier (e.g., H3 hex ID)."""

# SimId represents a unique identifier for simulation entities.
SimId = NewType("SimId", str)
"""Simulation object identifier with format 'ClassName_id'."""
