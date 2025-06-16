"""
Run all benchmark scripts in the benchmarks directory.

This script discovers and runs all benchmark scripts matching 'bench_*.py' in the current directory. Optionally, a filter string can be provided as a command-line argument to only run benchmarks whose filenames contain the filter.

Examples
--------
Run all benchmarks::

    python run_all.py

Run only benchmarks containing 'geodesic' in the filename::

    python run_all.py geodesic
"""

import glob
import os
import runpy
import sys


def main() -> None:
    """
    Discover and run all benchmark scripts matching 'bench_*.py' in the current directory.

    If a filter string is provided as a command-line argument, only benchmarks whose filenames contain the filter will be run.

    Returns
    -------
    None
    """
    filter_str: str = sys.argv[1] if len(sys.argv) > 1 else ""
    benchmark_dir: str = os.path.dirname(__file__)

    pattern: str = os.path.join(benchmark_dir, "bench_*.py")

    benchmark_files: list[str] = sorted(glob.glob(pattern))

    matched: list[str] = [
        f for f in benchmark_files if filter_str in os.path.basename(f)
    ]

    if not matched:
        print(f"No benchmark files matched '{filter_str}'")  # noqa: T201
        return

    for file in matched:
        print(f"\n=== Running {os.path.basename(file)} ===")  # noqa: T201
        runpy.run_path(file, run_name="__main__")


if __name__ == "__main__":
    main()
