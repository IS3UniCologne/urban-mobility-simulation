"""Run script for this project: the admission baselines a learning agent has to beat.

Each baseline runs the reinforcement learning environment with a fixed policy.
It reports the profit of the operator from the first decision point to the end of the episode and the service: fulfilled trips, lost users and their mean wait.
Train a policy on the same environment (see the README) and compare it with this table.
A plain project without a learning agent runs the simulation once through ``umosim run``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PROJECT_DIR.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from rl.problems import AdmissionProblem
    from scripts.rl_baselines import ADMISSION_BASELINES, format_table, sweep
except ImportError as exc:
    raise SystemExit(
        f"{exc}. The reinforcement learning harness needs the rl extra: uv sync --extra rl"
    ) from exc

# Simulation time an episode runs to (min): one day, about ten thousand decisions.
HORIZON_MIN = 1440
# Episode seeds. Every baseline runs once per seed; add seeds for tighter numbers.
SEEDS = [1, 2, 3]


def main() -> None:
    """Run every baseline over the seeds and print the table."""
    results = sweep(
        _PROJECT_DIR, AdmissionProblem(), ADMISSION_BASELINES, SEEDS, HORIZON_MIN
    )
    print(format_table(results))


if __name__ == "__main__":
    main()
