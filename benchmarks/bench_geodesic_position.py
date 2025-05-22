"""
Benchmarks for geodesic and Euclidean distance calculations.

This module benchmarks different methods for calculating distances between geodesic positions.

Examples
--------
Run this module directly to execute all benchmarks::

    python bench_geodesic_position.py
"""

import os
import sys
from collections.abc import Callable

import pyperf

# Ensure project root is in sys.path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from simulation.environment.geodesic_position import GeodesicPosition  # noqa: E402
from simulation.helper.random.random_manager import RandomManager  # noqa: E402

# Constants for random position generation (Berlin bounding box)
MIN_LAT: float = 52.3
MAX_LAT: float = 52.7
MIN_LNG: float = 13.1
MAX_LNG: float = 13.6
N_SAMPLES: int = 10000

POSITIONS: list[GeodesicPosition] = []
rand_manager = RandomManager()
for _ in range(N_SAMPLES * 2):
    lat = rand_manager.uniform(MIN_LAT, MAX_LAT)
    lng = rand_manager.uniform(MIN_LNG, MAX_LNG)
    POSITIONS.append(GeodesicPosition(lat, lng))


def bench_haversine() -> None:
    """
    Benchmark the Haversine distance calculation using the __rshift__ operator.

    Returns
    -------
    None
    """
    total = 0.0
    for i in range(0, len(POSITIONS), 2):
        total += POSITIONS[i].__rshift__(POSITIONS[i + 1])


def bench_euclidean() -> None:
    """
    Benchmark the Euclidean distance calculation using the __lshift__ operator.

    Returns
    -------
    None
    """
    total = 0.0
    for i in range(0, len(POSITIONS), 2):
        total += POSITIONS[i].__lshift__(POSITIONS[i + 1])


BENCHMARKS: list[tuple[str, Callable[[], None]]] = [
    ("haversine_distance", bench_haversine),
    ("euclidean_distance", bench_euclidean),
]


def main() -> None:
    """
    Run all registered benchmarks using pyperf.Runner.

    Returns
    -------
    None
    """
    runner = pyperf.Runner(values=3, loops=20)
    for name, func in BENCHMARKS:
        runner.bench_func(name, func)


if __name__ == "__main__":
    main()
