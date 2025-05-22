"""
Generic benchmark template for the benchmarks directory.

This template provides a structure for benchmarking any functionality using pyperf. Copy and adapt this file for new benchmarks as needed.

Examples
--------
To use this template, copy it and modify the benchmark functions and constants as required for your use case.

    cp bench_template.py bench_myfeature.py
    # Edit bench_myfeature.py as needed
    python bench_myfeature.py
"""

import os
import sys
from collections.abc import Callable

import pyperf

# Ensure project root is in sys.path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import simuliation modules here
# from simulation.this.that import these  # noqa: E402

# Define any constants or setup needed for your benchmarks here


def bench_example() -> None:
    """
    Benchmark an example operation.

    Replace this with your actual benchmark logic.

    Returns
    -------
    None
    """
    pass  # Replace with benchmark code


BENCHMARKS: list[tuple[str, Callable[[], None]]] = [
    ("example_benchmark", bench_example)
]


def main() -> None:
    """
    Run all registered benchmarks using pyperf.Runner.

    Returns
    -------
    None
    """
    runner = pyperf.Runner()
    for name, func in BENCHMARKS:
        runner.bench_func(name, func)


if __name__ == "__main__":
    main()
