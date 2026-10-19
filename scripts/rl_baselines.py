"""Sweep of the admission baselines over seeds, reporting profit and service.

Every trained policy has to beat these numbers on the same project and seeds.
The baselines answer ``AdmissionProblem`` on a project whose search engine is ``BrokeredAdmissionSearchEngine``.
The profit of an episode is the sum of the period profits the problem reports in ``info``, from the first decision point to the end.
It is therefore the same number whichever reward the problem pays.

Example::

    python scripts/rl_baselines.py data/projects/ridehailing_admission_demo --seeds 10
"""

from __future__ import annotations

import argparse
import os
import statistics
import time
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gymnasium as gym
import numpy as np
from gymnasium.vector import AsyncVectorEnv

from rl.env import UmosimEnv
from rl.operator_problem import OperatorProblem
from rl.problems import AdmissionProblem
from rl.problems.admission import DEFER, OFFER
from rl.problems.admission import FEATURES as ADMISSION_FEATURES
from rl.problems.features import unsquash

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from simulation.simulation import Simulation


Policy = Callable[["NDArray[np.float32]"], Any]
"""Mapping from one observation to one action."""

NEARBY_SHARE = 0.3
"""Pickup leg, as a share of the pickup radius, up to which the nearby baselines offer."""

IDLE_SHARE = 0.1
"""Standby share of the fleet from which the busy-aware baseline offers every search."""

DEADHEAD_MULTIPLE = 1.0
"""Pickup leg, as a multiple of the trip, up to which the deadhead baseline offers."""

_STANDBY = ADMISSION_FEATURES.index("standby")
_PICKUP = ADMISSION_FEATURES.index("pickup")
_TRIP = ADMISSION_FEATURES.index("trip")


def always(action: int) -> Policy:
    """Return a policy answering every search with one admission action."""
    return lambda observation: action


def nearby(observation: NDArray[np.float32]) -> int:
    """Offer a search whose shortest pickup leg is within ``NEARBY_SHARE`` of the radius."""
    return OFFER if observation[_PICKUP] <= NEARBY_SHARE else DEFER


def nearby_when_busy(observation: NDArray[np.float32]) -> int:
    """Offer every search while ``IDLE_SHARE`` of the fleet stands by, else nearby ones."""
    if observation[_STANDBY] >= IDLE_SHARE:
        return OFFER
    return nearby(observation)


def deadhead(observation: NDArray[np.float32]) -> int:
    """Offer a search whose shortest pickup leg is at most ``DEADHEAD_MULTIPLE`` times its trip.

    The trip entry is squashed against the radius, so unsquashed it is on the scale of the pickup entry.
    A trip entry at the top of the space stands for a trip beyond any pickup leg.
    """
    trip_share = unsquash(float(observation[_TRIP]))
    return OFFER if observation[_PICKUP] <= DEADHEAD_MULTIPLE * trip_share else DEFER


@dataclass(frozen=True, slots=True)
class Outcome:
    """
    Result of one episode.

    Attributes
    ----------
    profit : float
        Profit of the learning agent's operator from the first decision point to
        the end of the episode, summed from the period profits in ``info``.
    fulfilled : int
        Trips the learning agent's operator fulfilled after the first decision
        point, summed from ``info``.
    lost : int
        Users whose search ran out unserved, from the world's user log.
    wait_min : float
        Mean wait of the served users (min), zero when none was served.
    """

    profit: float
    fulfilled: int
    lost: int
    wait_min: float


ADMISSION_BASELINES: dict[str, Policy | None] = {
    "offer": always(OFFER),
    "nearby": nearby,
    "nearby_when_busy": nearby_when_busy,
    "deadhead": deadhead,
    "random": None,
}
"""Admission baselines by name. None samples the action space."""


def run_episode(env: UmosimEnv, policy: Policy | None, seed: int) -> Outcome:
    """Drive one episode with a policy and return its outcome.

    Parameters
    ----------
    env : UmosimEnv
        Environment to reset and step.
    policy : Policy or None
        Policy mapping each observation to an action. None samples the action
        space, seeded with the episode seed.
    seed : int
        Episode seed.

    Returns
    -------
    Outcome
        Profit and service of the episode.

    Raises
    ------
    TypeError
        If the problem of the environment is not an ``OperatorProblem``, whose
        ``info`` reports the profit and fulfilled trips of each period.
    """
    if not isinstance(env.problem, OperatorProblem):
        msg = f"{type(env.problem).__name__} is not an OperatorProblem, so it settles no profit."
        raise TypeError(msg)
    observation, _ = env.reset(seed=seed)
    env.action_space.seed(seed)
    if policy is None:
        policy = lambda observation: env.action_space.sample()  # noqa: E731
    profit = 0.0
    fulfilled = 0
    while True:
        observation, _, terminated, truncated, info = env.step(policy(observation))
        profit += info["profit"]
        fulfilled += info["fulfilled"]
        if terminated or truncated:
            return _outcome(_simulation(env), profit, fulfilled)


def _simulation(env: UmosimEnv) -> Simulation:
    """Return the simulation of the running episode."""
    simulation = env.simulation
    if simulation is None:
        msg = "No episode is running, call reset() first."
        raise RuntimeError(msg)
    return simulation


def _outcome(simulation: Simulation, profit: float, fulfilled: int) -> Outcome:
    """Return the outcome of the episode that just ended, the service from the user log's statistics."""
    stats = simulation.world.user_log.metrics
    return Outcome(profit, fulfilled, stats.total_missed_trips, stats.average_wait_time)


def sweep(
    project: Path | str,
    problem: OperatorProblem[Any, Any],
    policies: Mapping[str, Policy | None],
    seeds: list[int],
    horizon_min: int | None,
) -> dict[str, list[Outcome]]:
    """Run every policy over every seed on one environment.

    Parameters
    ----------
    project : Path or str
        Project directory the environment is built from.
    problem : OperatorProblem
        Problem the environment is built around, the one the project is wired for.
    policies : mapping of str to Policy or None
        Policies by name. None samples the action space.
    seeds : list of int
        Episode seeds, shared by all policies.
    horizon_min : int or None
        Simulation time an episode stops at (min). None takes the project's END_TIME.

    Returns
    -------
    dict of str to list of Outcome
        Episode outcomes per policy in seed order.
    """
    with UmosimEnv(project, problem, horizon_min=horizon_min) as env:
        return {
            name: [run_episode(env, policy, seed) for seed in seeds]
            for name, policy in policies.items()
        }


class _OutcomeOnEnd(gym.Wrapper):
    """Add the episode's lost users and mean wait to the info of its last step."""

    def step(self, action):  # noqa: ANN202, ANN001
        observation, reward, terminated, truncated, info = self.env.step(action)
        if terminated or truncated:
            stats = self.env.unwrapped.simulation.world.user_log.metrics
            info = {
                **info,
                "lost": stats.total_missed_trips,
                "wait_min": stats.average_wait_time,
            }
        return observation, reward, terminated, truncated, info


def async_sweep(
    project: Path | str,
    problem: OperatorProblem[Any, Any],
    policies: Mapping[str, Policy | None],
    seeds: list[int],
    in_parallel: int,
    horizon_min: int | None,
) -> dict[str, list[Outcome]]:
    """Run every policy over every seed on AsyncVectorEnv.

    Parameters
    ----------
    project : Path or str
        Project directory the environment is built from.
    problem : OperatorProblem
        Problem the environment is built around, the one the project is wired for.
    policies : mapping of str to Policy or None
        Policies by name. None samples the action space.
    seeds : list of int
        Episode seeds, shared by all policies.
    in_parallel : int
        Number of parallel evaluations, -1 uses all available cores.
    horizon_min : int or None
        Simulation time an episode stops at (min). None takes the project's END_TIME.

    Returns
    -------
    dict of str to list of Outcome
        Episode outcomes per policy in seed order.
    """
    n_processes = in_parallel if in_parallel > 0 else os.cpu_count()
    batched_seeds = [
        list(batch) for batch in batched(seeds, n_processes)
    ]  # python 3.12+
    returns = defaultdict(list)
    for policy_name, policy in policies.items():
        print(f"Running {policy_name}...")
        for batch in batched_seeds:
            envs = AsyncVectorEnv(
                [
                    lambda: _OutcomeOnEnd(
                        UmosimEnv(project, problem, horizon_min=horizon_min)
                    )
                    for _ in range(len(batch))
                ]
            )

            observation, _ = envs.reset(seed=batch)
            done = np.zeros(len(batch), dtype=bool)
            envs.action_space.seed(
                batch[0]
            )  # attention: not comparable with sequential
            profits = np.zeros(len(batch), dtype=np.float32)
            fulfilled = np.zeros(len(batch), dtype=np.int32)
            lost = np.zeros(len(batch), dtype=np.int32)
            wait_min = np.zeros(len(batch), dtype=np.float32)
            while not all(done):
                if policy is None:
                    actions = envs.action_space.sample()
                else:
                    actions = np.array([policy(o) for o in observation])
                observation, _, terminated, truncated, info = envs.step(actions)
                live = ~done  # mask of the episodes that are still running
                profits[live] += info["profit"][live]
                fulfilled[live] += info["fulfilled"][live]
                ended = live & (terminated | truncated)
                if any(ended):
                    lost[ended] = info["lost"][ended]
                    wait_min[ended] = info["wait_min"][ended]
                done |= ended
            returns[policy_name].extend(
                Outcome(float(p), int(f), int(lo), float(w))
                for p, f, lo, w in zip(profits, fulfilled, lost, wait_min, strict=True)
            )
        envs.close()
    return returns


def format_table(results: dict[str, list[Outcome]]) -> str:
    """Return one line per baseline: mean and stdev of profit, then mean fulfilled, lost and wait."""
    lines = [
        f"{'baseline':16s} {'profit':>9s} {'stdev':>8s} {'fulfilled':>9s} {'lost':>7s} {'wait':>6s}"
    ]
    for name, outcomes in results.items():
        profits = [outcome.profit for outcome in outcomes]
        stdev = statistics.stdev(profits) if len(profits) > 1 else 0.0
        fulfilled = statistics.mean(outcome.fulfilled for outcome in outcomes)
        lost = statistics.mean(outcome.lost for outcome in outcomes)
        wait = statistics.mean(outcome.wait_min for outcome in outcomes)
        lines.append(
            f"{name:16s} {statistics.mean(profits):9.1f} {stdev:8.1f} "
            f"{fulfilled:9.1f} {lost:7.1f} {wait:6.1f}"
        )
    return "\n".join(lines)


def main() -> None:
    """Parse the arguments, run the sweep and print the table."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", type=Path, help="project directory with config.toml")
    parser.add_argument(
        "--seeds", type=int, default=10, help="number of seeds, 1 to N (default: 10)"
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=None,
        help="simulation time an episode stops at, in minutes (default: END_TIME)",
    )
    parser.add_argument(
        "--baselines",
        nargs="+",
        default=None,
        help="baselines to run, names from ADMISSION_BASELINES (default: all)",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=None,
        help="number of parallel evaluations, -1 uses all available cores, default is sequential (default: None)",
    )
    args = parser.parse_args()

    names = args.baselines or list(ADMISSION_BASELINES)
    unknown = sorted(set(names) - ADMISSION_BASELINES.keys())
    if unknown:
        parser.error(
            f"unknown baselines: {', '.join(unknown)}. "
            f"Choose from {', '.join(ADMISSION_BASELINES)}."
        )

    started = time.perf_counter()
    if args.parallel is not None:
        results = async_sweep(
            args.project,
            AdmissionProblem(),
            {name: ADMISSION_BASELINES[name] for name in names},
            list(range(1, args.seeds + 1)),
            args.parallel,
            args.horizon,
        )
    else:
        results = sweep(
            args.project,
            AdmissionProblem(),
            {name: ADMISSION_BASELINES[name] for name in names},
            list(range(1, args.seeds + 1)),
            args.horizon,
        )
    print(format_table(results))
    print(f"{time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
