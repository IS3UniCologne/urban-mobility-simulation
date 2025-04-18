import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from simulation.helper.solvers.tsp_solver_2opt import solve_tsp

sys.argv = [
    sys.argv[0],
    "resources/configurations/config_template.toml",
]  # Add a path to a test config file


class TestSolveTSP(unittest.TestCase):
    def setUp(self):
        # Mock environment and other dependencies
        self.env = MagicMock()

        # Create a simple distance matrix for testing
        # Using hex IDs as indices
        hex_ids = [
            "871f1d488ffffff",
            "871f1d489ffffff",
            "871f1d48affffff",
            "871f1d48bffffff",
        ]
        distances = [
            [0, 500, 1000, 1500],
            [500, 0, 700, 1200],
            [1000, 700, 0, 600],
            [1500, 1200, 600, 0],
        ]
        self.distance_matrix = pd.DataFrame(distances, index=hex_ids, columns=hex_ids)

    @patch("simulation.helper.random.random_manager.RandomManager")
    def test_solve_tsp_returns_valid_solution(self, mock_random_manager):
        # Set up mock RandomManager
        mock_instance = MagicMock()
        mock_instance.integers.return_value = 42  # Fixed seed for reproducibility
        mock_random_manager.return_value = mock_instance

        # Create a test case with four hexagons
        hexagons = {
            "871f1d488ffffff": 0,
            "871f1d489ffffff": 1,
            "871f1d48affffff": 2,
            "871f1d48bffffff": 3,
        }

        # Call the method under test
        best_state, best_fitness, dist_lookup = solve_tsp(
            hexagons, self.distance_matrix
        )

        # Verify the result
        self.assertEqual(len(best_state), 4, "TSP solution should visit all 4 hexagons")
        self.assertTrue(
            all(idx in best_state for idx in range(4)),
            "All hexagon indices should be present in the solution",
        )
        (
            self.assertIsInstance(best_fitness, (int, float, np.float64, np.int64)),
            "Fitness should be a numeric value",
        )
        self.assertGreaterEqual(best_fitness, 0, "Fitness should be non-negative")

        # Check that dist_list contains correct entries
        self.assertEqual(
            len(dist_lookup), 12, "Should have n*(n-1) distances for n hexagons"
        )

        # Verify that all pairs are included
        pairs = [(i, j) for i in range(4) for j in range(4) if i != j]
        for key in dist_lookup.keys():
            self.assertIn(
                key,
                pairs,
                f"Distance entry {key[0]}->{key[1]} should be in expected pairs",
            )
        # Verify path continuity (each node connects to another)
        for i in range(len(best_state) - 1):
            current = best_state[i]
            next_node = best_state[i + 1]
            # Check that the edge exists in the distance lookup
            self.assertIn(
                (current, next_node),
                dist_lookup,
                f"Missing connection from {current} to {next_node}",
            )

    @patch("simulation.helper.random.random_manager.RandomManager")
    def test_solve_tsp_small_case(self, mock_random_manager):
        # Test with the smallest possible TSP (2 nodes)
        mock_instance = MagicMock()
        mock_instance.integers.return_value = 42
        mock_random_manager.return_value = mock_instance

        hexagons = {"871f1d488ffffff": 0, "871f1d489ffffff": 1}

        best_state, best_fitness, dist_lookup = solve_tsp(
            hexagons, self.distance_matrix
        )

        self.assertEqual(len(best_state), 2, "Should have exactly 2 nodes in path")
        self.assertIn(0, best_state, "Node 0 should be in the path")
        self.assertIn(1, best_state, "Node 1 should be in the path")
        self.assertEqual(len(dist_lookup), 2, "Should have exactly 2 distance entries")

        # The distance should match our distance matrix - round trip distance for a TSP
        # For a 2-node problem, the fitness is the round trip: A→B + B→A = 500 + 500 = 1000
        expected_distance = 1000  # Round trip distance from our distance matrix
        self.assertEqual(
            best_fitness,
            expected_distance,
            "For a 2-node TSP, fitness should equal the round trip distance between nodes",
        )

    def test_solve_tsp_six_nodes(self):
        """Test TSP solver with a larger 6-node problem."""

        # Create a 6-node distance matrix
        hex_ids = [
            "871f1d488ffffff",  # 0
            "871f1d489ffffff",  # 1
            "871f1d48affffff",  # 2
            "871f1d48bffffff",  # 3
            "871f1d48cffffff",  # 4
            "871f1d48dffffff",  # 5
        ]
        distances = [
            [0, 500, 1000, 1500, 1200, 900],  # From node 0
            [500, 0, 700, 1200, 800, 1100],  # From node 1
            [1000, 700, 0, 600, 400, 800],  # From node 2
            [1500, 1200, 600, 0, 500, 700],  # From node 3
            [1200, 800, 400, 500, 0, 300],  # From node 4
            [900, 1100, 800, 700, 300, 0],  # From node 5
        ]
        larger_distance_matrix = pd.DataFrame(distances, index=hex_ids, columns=hex_ids)

        # Create test hexagons dictionary
        hexagons = {
            "871f1d488ffffff": 0,
            "871f1d489ffffff": 1,
            "871f1d48affffff": 2,
            "871f1d48bffffff": 3,
            "871f1d48cffffff": 4,
            "871f1d48dffffff": 5,
        }

        # Call the method under test
        best_state, best_fitness, dist_lookup = solve_tsp(
            hexagons, larger_distance_matrix
        )

        # Verify the solution structure
        self.assertEqual(len(best_state), 6, "TSP solution should visit all 6 hexagons")
        self.assertTrue(
            all(idx in best_state for idx in range(6)),
            "All hexagon indices should be present in the solution",
        )
        self.assertIsInstance(
            best_fitness,
            (int, float, np.float64, np.int64),
            "Fitness should be a numeric value",
        )
        self.assertGreaterEqual(best_fitness, 0, "Fitness should be non-negative")

        # Verify that the distance list contains all necessary edges
        self.assertEqual(
            len(dist_lookup), 30, "Should have n*(n-1) distances for 6 nodes"
        )

        # Verify that the solution is better than a naive tour
        # naive_tour = [0, 1, 2, 3, 4, 5]
        naive_distance = 500 + 700 + 600 + 500 + 300 + 900  # Complete cycle
        self.assertLessEqual(
            best_fitness,
            naive_distance,
            "Optimized solution should be at least as good as the naive tour",
        )

        # Verify path integrity/continuity
        for i in range(len(best_state) - 1):
            current = best_state[i]
            next_node = best_state[i + 1]
            # There should be a valid distance between consecutive nodes
            self.assertIn(
                (current, next_node),
                dist_lookup,
                f"Invalid edge in solution path: {current}->{next_node}",
            )

        # Check the last-to-first connection to complete the cycle
        self.assertIn(
            (best_state[-1], best_state[0]),
            dist_lookup,
            "The tour should form a complete cycle",
        )


if __name__ == "__main__":
    unittest.main()
