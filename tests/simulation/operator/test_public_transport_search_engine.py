"""Tests for the stop check of PublicTransportSearchEngine."""

from unittest.mock import Mock

import h3
import pytest

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.operator.public_transport_search_engine import (
    PublicTransportSearchEngine,
)

pytestmark = pytest.mark.unit

HEX = "871f1d496ffffff"
# inside the flat polygon of HEX, but h3 puts it in a neighbouring hexagon
EDGE_POINT = (52.49372635471426, 13.162835656628483)


def test_stop_is_near_only_in_its_h3_hexagon() -> None:
    sim = Mock()
    sim.config.world.SPATIAL_RESOLUTION = 7
    centre = GeodesicPosition(sim, *h3.cell_to_latlng(HEX))
    edge_stop = GeodesicPosition(sim, *EDGE_POINT)
    centre_stop = GeodesicPosition(sim, *h3.cell_to_latlng(HEX))
    stops = [edge_stop, centre_stop]
    vehicle = Mock()
    vehicle.route.route_stops = stops
    engine = PublicTransportSearchEngine.__new__(PublicTransportSearchEngine)

    viable = engine._check_viable_stops(vehicle, "hexagon", centre, centre)

    assert viable == {"origin": [centre_stop], "destination": [centre_stop]}
