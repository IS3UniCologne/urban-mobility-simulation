"""TSP solver using the 2-opt algorithm.

This module provides functionality for solving the Traveling Salesman Problem
using the 2-opt local search heuristic for route optimization.
"""

from typing import NamedTuple, cast

import pandas as pd


class TspResult(NamedTuple):
    """Result of TSP solver containing the optimized tour and related data.

    Attributes
    ----------
    tour_sequence : list of int
        The sequence of node indices representing the optimized tour.
    tour_length : float
        The total length/cost of the optimized tour.
    distance_lookup : dict of tuple of int, int to float
        Dictionary mapping node pairs to their distances for fast lookup.
    """

    tour_sequence: list[int]
    tour_length: float
    distance_lookup: dict[tuple[int, int], float]


def solve_tsp(hexagons: dict[str, int], distance_matrix: pd.DataFrame) -> TspResult:
    """Solve the Traveling Salesman Problem for a given set of hexagons using the 2-opt algorithm.

    TODO: Implement Lin-Kernighan heuristic or 3-opt and make configurable.

    :param hexagons: Dictionary mapping hexagon IDs to indices
    :param distance_matrix: Distance matrix between hexagons
    :return: Optimized tour sequence, tour cost, and distance lookup dictionary
    """
    # Create a distance lookup dictionary for faster access
    dist_lookup: dict[tuple[int, int], float] = {}
    for hex_i, value_i in hexagons.items():
        for hex_j, value_j in hexagons.items():
            if hex_i != hex_j:
                val = cast("float", distance_matrix.at[hex_j, hex_i])
                dist_lookup[(value_i, value_j)] = val
                dist_lookup[(value_j, value_i)] = val

    n = len(hexagons)

    # Initialize with a simple sequential tour
    tour_sequence = list(range(n))

    # If there are 3 or fewer nodes, no need for optimization
    if n > 3:
        # Calculate initial tour length
        tour_length = calculate_tour_length(tour_sequence, dist_lookup)

        # Apply 2-opt improvement
        improved = True
        # Limit iterations, should realistically never reach this in our use case
        max_iterations = 100
        iterations = 0

        while improved and iterations < max_iterations:
            improved = False
            iterations += 1

            for i in range(n - 2):
                for j in range(i + 2, n):
                    # Consider swapping edges (i,i+1) and (j,j+1)
                    # Where j+1 wraps around to 0 if j is the last index
                    current_cost = dist_lookup.get(
                        (tour_sequence[i], tour_sequence[i + 1]), 0
                    ) + dist_lookup.get(
                        (tour_sequence[j], tour_sequence[(j + 1) % n]), 0
                    )
                    new_cost = dist_lookup.get(
                        (tour_sequence[i], tour_sequence[j]), 0
                    ) + dist_lookup.get(
                        (tour_sequence[i + 1], tour_sequence[(j + 1) % n]), 0
                    )

                    if new_cost < current_cost:
                        # Reverse the segment between i+1 and j
                        tour_sequence[i + 1 : j + 1] = reversed(
                            tour_sequence[i + 1 : j + 1]
                        )
                        tour_length = tour_length - current_cost + new_cost
                        improved = True
                        break

                if improved:
                    break

    # Calculate final tour  (length)
    tour_length = calculate_tour_length(tour_sequence, dist_lookup)

    return TspResult(
        tour_sequence=tour_sequence,
        tour_length=tour_length,
        distance_lookup=dist_lookup,
    )


def calculate_tour_length(
    tour: list[int], dist_lookup: dict[tuple[int, int], float]
) -> float:
    """
    Calculate the total length of a tour.

    :param tour: A list of node indices representing the tour
    :param dist_lookup: Dictionary mapping node pairs to distances
    :return: Total tour length
    """
    length: float = 0.0
    n: int = len(tour)

    for i in range(n):
        j = (i + 1) % n  # Next node (wraps around)
        length += dist_lookup.get((tour[i], tour[j]), 0.0)

    return length
