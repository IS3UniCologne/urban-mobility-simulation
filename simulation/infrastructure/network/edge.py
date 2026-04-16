from __future__ import annotations  # noqa: D100

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition


class Edge:  # noqa: D101
    __slots__ = ("_destination", "_distance", "_origin")

    def __init__(
        self, distance: float, origin: GeodesicPosition, destination: GeodesicPosition
    ) -> None:
        self._distance = distance
        self._origin = origin
        self._destination = destination

    @property
    def distance(self) -> float:  # noqa: D102
        return self._distance

    @property
    def origin(self) -> GeodesicPosition:  # noqa: D102
        return self._origin

    @property
    def destination(self) -> GeodesicPosition:
        """Get the destination position of the edge."""
        return self._destination
