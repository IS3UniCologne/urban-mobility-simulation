import random
import statistics
import time
import unittest

import matplotlib.pyplot as plt
import pytest

from simulation.environment.geodesic_position import GeodesicPosition

pytestmark = pytest.mark.skip(reason="Performance tests, run manually")


class TestGeodesicPositionDistance(unittest.TestCase):
    """Tests for GeodesicPosition distance calculations"""

    def test_distance_calculation_speed(self):
        """Compare performance of haversine vs euclidean distance calculations"""
        # Berlin's approximate bounding box
        min_lat, max_lat = 52.3, 52.7  # latitude range
        min_lng, max_lng = 13.1, 13.6  # longitude range

        # Number of position pairs to test
        n_samples = 10000

        # Generate random positions within Berlin
        positions = []
        for _ in range(n_samples * 2):
            lat = random.uniform(min_lat, max_lat)
            lng = random.uniform(min_lng, max_lng)
            positions.append(GeodesicPosition(lat, lng))

        # Measure time for haversine distance (>>)
        start_time = time.time()
        haversine_distances = []
        for i in range(0, len(positions), 2):
            haversine_distances.append(positions[i] >> positions[i + 1])
        haversine_time = time.time() - start_time

        # Measure time for euclidean distance (<<)
        start_time = time.time()
        euclidean_distances = []
        for i in range(0, len(positions), 2):
            euclidean_distances.append(positions[i] << positions[i + 1])
        euclidean_time = time.time() - start_time

        # Report results
        print(f"\nPerformance comparison over {n_samples} distance calculations:")
        print(f"Haversine (>>) time: {haversine_time:.4f} seconds")
        print(f"Euclidean (<<) time: {euclidean_time:.4f} seconds")
        print(f"Speedup factor: {haversine_time / euclidean_time:.2f}x")

        # Verify that euclidean is actually faster
        self.assertLess(
            euclidean_time,
            haversine_time,
            "Euclidean distance calculation should be faster than haversine",
        )

    def test_distance_calculation_accuracy(self):
        """Compare accuracy of euclidean approximation vs haversine for Berlin distances"""
        # Berlin's approximate bounding box
        min_lat, max_lat = 52.3, 52.7  # latitude range
        min_lng, max_lng = 13.1, 13.6  # longitude range

        # Number of position pairs to test
        n_samples = 1000

        # Generate random positions within Berlin
        positions = []
        for _ in range(n_samples * 2):
            lat = random.uniform(min_lat, max_lat)
            lng = random.uniform(min_lng, max_lng)
            positions.append(GeodesicPosition(lat, lng))

        # Calculate distances using both methods
        haversine_distances = []
        euclidean_distances = []
        for i in range(0, len(positions), 2):
            haversine_distances.append(positions[i] >> positions[i + 1])
            euclidean_distances.append(positions[i] << positions[i + 1])

        # Calculate relative errors
        relative_errors = [
            (e - h) / h for h, e in zip(haversine_distances, euclidean_distances)
        ]
        absolute_errors = [
            abs(e - h) for h, e in zip(haversine_distances, euclidean_distances)
        ]

        # Calculate statistics
        avg_rel_error = statistics.mean(relative_errors) * 100  # as percentage
        max_rel_error = max(relative_errors) * 100  # as percentage
        min_rel_error = min(relative_errors) * 100  # as percentage
        std_rel_error = statistics.stdev(relative_errors) * 100  # as percentage

        avg_abs_error = statistics.mean(absolute_errors)  # in meters
        max_abs_error = max(absolute_errors)  # in meters

        # Report results
        print("\nAccuracy of euclidean distance as approximation of haversine:")
        print(f"Average relative error: {avg_rel_error:.2f}%")
        print(f"Maximum relative error: {max_rel_error:.2f}%")
        print(f"Minimum relative error: {min_rel_error:.2f}%")
        print(f"Standard deviation of relative error: {std_rel_error:.2f}%")
        print(f"Average absolute error: {avg_abs_error:.2f} meters")
        print(f"Maximum absolute error: {max_abs_error:.2f} meters")

        # Create visualization
        plt.figure(figsize=(12, 10))

        # Plot 1: Scatter plot comparing distances
        plt.subplot(2, 2, 1)
        plt.scatter(haversine_distances, euclidean_distances, alpha=0.5)
        max_dist = max(max(haversine_distances), max(euclidean_distances))
        plt.plot([0, max_dist], [0, max_dist], "r--")
        plt.xlabel("Haversine Distance (m)")
        plt.ylabel("Euclidean Distance (m)")
        plt.title("Comparison of Distance Calculations")

        # Plot 2: Histogram of relative errors
        plt.subplot(2, 2, 2)
        plt.hist(relative_errors, bins=50)
        plt.xlabel("Relative Error")
        plt.ylabel("Frequency")
        plt.title("Distribution of Relative Errors")

        # Plot 3: Relative error vs distance
        plt.subplot(2, 2, 3)
        plt.scatter(haversine_distances, relative_errors, alpha=0.5)
        plt.axhline(y=0, color="r", linestyle="--")
        plt.xlabel("Haversine Distance (m)")
        plt.ylabel("Relative Error")
        plt.title("Relative Error vs. Distance")

        # Plot 4: Absolute error vs distance
        plt.subplot(2, 2, 4)
        plt.scatter(haversine_distances, absolute_errors, alpha=0.5)
        plt.xlabel("Haversine Distance (m)")
        plt.ylabel("Absolute Error (m)")
        plt.title("Absolute Error vs. Distance")

        plt.tight_layout()
        plt.savefig("distance_comparison.png")

        # Verify that the euclidean approximation is reasonably accurate for Berlin
        self.assertLess(
            abs(avg_rel_error), 5, "Average relative error should be less than 5%"
        )
        self.assertLess(
            avg_abs_error, 100, "Average absolute error should be less than 100 meters"
        )


if __name__ == "__main__":
    unittest.main()
