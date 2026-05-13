"""Tests for GeodesicPosition distance calculations."""

import random
import statistics
from unittest.mock import Mock

import pytest

from simulation.environment.geodesic_position import GeodesicPosition


@pytest.fixture
def mock_sim() -> Mock:
    """Create a mock simulation context for testing."""
    mock_sim = Mock()
    mock_sim.config.world.SPATIAL_RESOLUTION = 7
    return mock_sim


@pytest.mark.unit
class TestGeodesicPositionDistance:
    """Tests for GeodesicPosition distance calculations."""

    def test_distance_calculation_speed(self, mock_sim: Mock) -> None:
        """Test that euclidean distance calculation is faster than haversine."""
        # Berlin's approximate bounding box
        min_lat, max_lat = 52.3, 52.7  # latitude range
        min_lng, max_lng = 13.1, 13.6  # longitude range

        # Number of position pairs to test
        n_samples = 1000  # Reduced for faster test execution

        # Generate random positions within Berlin
        positions = []
        for _ in range(n_samples * 2):
            lat = random.uniform(min_lat, max_lat)
            lng = random.uniform(min_lng, max_lng)
            positions.append(GeodesicPosition(mock_sim, lat, lng))

        # Measure haversine distance calculations
        import time

        start_time = time.time()
        for i in range(0, len(positions), 2):
            _ = positions[i] >> positions[i + 1]
        haversine_time = time.time() - start_time

        # Measure euclidean distance calculations
        start_time = time.time()
        for i in range(0, len(positions), 2):
            _ = positions[i] << positions[i + 1]
        euclidean_time = time.time() - start_time

        # Verify that euclidean is actually faster
        assert euclidean_time < haversine_time, (
            "Euclidean distance calculation should be faster than haversine"
        )

    def test_distance_calculation_accuracy(self, mock_sim: Mock) -> None:
        """Test accuracy of euclidean approximation vs haversine for Berlin distances."""
        # Berlin's approximate bounding box
        min_lat, max_lat = 52.3, 52.7  # latitude range
        min_lng, max_lng = 13.1, 13.6  # longitude range

        # Number of position pairs to test
        n_samples = 500  # Reduced for faster test execution

        # Generate random positions within Berlin
        positions = []
        for _ in range(n_samples * 2):
            lat = random.uniform(min_lat, max_lat)
            lng = random.uniform(min_lng, max_lng)
            positions.append(GeodesicPosition(mock_sim, lat, lng))

        # Calculate distances using both methods
        haversine_distances = []
        euclidean_distances = []
        for i in range(0, len(positions), 2):
            haversine_distances.append(positions[i] >> positions[i + 1])
            euclidean_distances.append(positions[i] << positions[i + 1])

        # Calculate relative and absolute errors
        relative_errors = [
            (e - h) / h for h, e in zip(haversine_distances, euclidean_distances)
        ]
        absolute_errors = [
            abs(e - h) for h, e in zip(haversine_distances, euclidean_distances)
        ]

        # Calculate statistics
        avg_rel_error = statistics.mean(relative_errors) * 100  # as percentage
        avg_abs_error = statistics.mean(absolute_errors)  # in meters

        # Verify that the euclidean approximation is reasonably accurate for Berlin
        assert abs(avg_rel_error) < 5, (
            f"Average relative error should be less than 5%, got {avg_rel_error:.2f}%"
        )
        assert avg_abs_error < 100, (
            f"Average absolute error should be less than 100 meters, got {avg_abs_error:.2f} meters"
        )

    def test_basic_distance_calculations(self, mock_sim: Mock) -> None:
        """Test basic distance calculation functionality."""
        # Create two positions in Berlin
        pos1 = GeodesicPosition(mock_sim, 52.5200, 13.4050)  # Berlin center
        pos2 = GeodesicPosition(mock_sim, 52.5170, 13.3888)  # Brandenburg Gate

        # Calculate distances
        haversine_distance = pos1 >> pos2
        euclidean_distance = pos1 << pos2

        # Both distances should be positive
        assert haversine_distance > 0, "Haversine distance should be positive"
        assert euclidean_distance > 0, "Euclidean distance should be positive"

        # For short distances in Berlin, euclidean should be close to haversine
        relative_error = (
            abs(euclidean_distance - haversine_distance) / haversine_distance
        )
        assert relative_error < 0.05, (
            f"Relative error between methods should be < 5% for Berlin distances, "
            f"got {relative_error * 100:.2f}%"
        )

    def test_same_position_distance(self, mock_sim: Mock) -> None:
        """Test that distance from a position to itself is zero."""
        pos = GeodesicPosition(mock_sim, 52.5200, 13.4050)

        haversine_distance = pos >> pos
        euclidean_distance = pos << pos

        assert haversine_distance == 0, (
            "Haversine distance to same position should be zero"
        )
        assert euclidean_distance == 0, (
            "Euclidean distance to same position should be zero"
        )

    @pytest.mark.parametrize(
        "lat1,lng1,lat2,lng2",
        [
            (52.5200, 13.4050, 52.5170, 13.3888),  # Berlin center to Brandenburg Gate
            (52.3, 13.1, 52.7, 13.6),  # Berlin bounding box corners
            (52.4, 13.2, 52.6, 13.5),  # Other Berlin positions
        ],
    )
    def test_distance_symmetry(
        self, mock_sim: Mock, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> None:
        """Test that distance calculation is symmetric."""
        pos1 = GeodesicPosition(mock_sim, lat1, lng1)
        pos2 = GeodesicPosition(mock_sim, lat2, lng2)

        # Distance from pos1 to pos2 should equal distance from pos2 to pos1
        assert (pos1 >> pos2) == (pos2 >> pos1), (
            "Haversine distance should be symmetric"
        )
        assert (pos1 << pos2) == (pos2 << pos1), (
            "Euclidean distance should be symmetric"
        )

    def test_distance_triangle_inequality(self, mock_sim: Mock) -> None:
        """Test that distances satisfy triangle inequality."""
        pos1 = GeodesicPosition(mock_sim, 52.5200, 13.4050)  # Berlin center
        pos2 = GeodesicPosition(mock_sim, 52.5170, 13.3888)  # Brandenburg Gate
        pos3 = GeodesicPosition(mock_sim, 52.5243, 13.4105)  # Museum Island

        # Triangle inequality: distance(A,C) <= distance(A,B) + distance(B,C)
        haversine_ac = pos1 >> pos3
        haversine_ab = pos1 >> pos2
        haversine_bc = pos2 >> pos3

        euclidean_ac = pos1 << pos3
        euclidean_ab = pos1 << pos2
        euclidean_bc = pos2 << pos3

        assert haversine_ac <= haversine_ab + haversine_bc, (
            "Haversine distances should satisfy triangle inequality"
        )
        assert euclidean_ac <= euclidean_ab + euclidean_bc, (
            "Euclidean distances should satisfy triangle inequality"
        )
