"""Tests for the position of a charging station."""

from unittest.mock import Mock

import h3
import pytest
import simpy

from simulation.infrastructure.charging_stations.charging_station import ChargingStation

pytestmark = pytest.mark.unit


def test_centre_is_the_point_vehicles_drive_to() -> None:
    # at resolution 5 the flat polygon centroid is about 4 m off the h3 centre
    location = h3.latlng_to_cell(41.88, -87.63, 5)
    sim = Mock()
    sim.env = simpy.Environment()
    sim.uid_manager.generate_uid.return_value = (1, "uid")
    sim.config.world.SPATIAL_RESOLUTION = 5
    sim.geo_env.get_centroid.side_effect = h3.cell_to_latlng

    station = ChargingStation(
        sim, Mock(), cs_id=0, location=location, power=50.0, capacity=1, queue_size=0
    )

    assert station.centre.getExactLocation() == h3.cell_to_latlng(location)
