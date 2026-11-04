"""Integration tests running the admission project through a real simulation."""

from __future__ import annotations

import os
import random
from itertools import pairwise
from typing import TYPE_CHECKING

import numpy as np
import pytest

pytest.importorskip("gymnasium")
pytest.importorskip("greenlet")

import gymnasium
from gymnasium.spaces import Box, Discrete, flatten

from rl.adapters import BrokeredAdmissionSearchEngine
from rl.channel import DecisionChannel
from rl.env import ENV_ID
from rl.problem import Period, Problem
from rl.problems import AdmissionProblem
from rl.problems.admission import OFFER
from simulation.operator.accounting import CostType
from tests.rl import HORIZON

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from numpy.typing import NDArray

    from rl.bookkeeper import SettlementPeriod
    from rl.channel import DecisionRequest
    from rl.env import UmosimEnv
    from simulation.helper.types import SimId
    from simulation.operator.data_transfer_object.transport_request import (
        TransportRequest,
    )
    from simulation.operator.data_transfer_object.transportation_alternative_browser import (
        TransportationAlternativeBrowser,
    )
    from simulation.simulation import Simulation

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def run_steps(env: UmosimEnv, seed: int, steps: int) -> list[tuple[float, float]]:
    """Run an episode with a seeded action sequence and return its trace."""
    observation, _ = env.reset(seed=seed)
    env.action_space.seed(0)
    trace = [(digest(env, observation), 0.0)]

    for _ in range(steps):
        observation, reward, terminated, truncated, _ = env.step(
            env.action_space.sample()
        )
        trace.append((digest(env, observation), round(reward, 6)))
        if terminated or truncated:
            break
    return trace


def digest(env: UmosimEnv, observation: object) -> float:
    """Reduce an observation of any space to one comparable number."""
    return round(float(flatten(env.observation_space, observation).sum()), 6)


class Recording(AdmissionProblem):
    """AdmissionProblem recording every settlement it closed."""

    def __init__(self) -> None:
        super().__init__()
        self.closed: list[SettlementPeriod] = []

    def close_period(self, simulation: Simulation, period: Period) -> None:
        """Close the period, then record its settlement."""
        super().close_period(simulation, period)
        self.closed.append(self.settlement)


class Stopwatch(Problem["NDArray[np.float32]", np.int64]):
    """Problem without an operator: offers every search and rewards the minutes each period lasts.

    Keeps the default ``close_period`` and ``on_request``, so it reads nothing but the bounds.
    """

    @property
    def observation_space(self) -> Box:
        """Return the period length (min)."""
        return Box(0.0, np.inf, shape=(1,), dtype=np.float32)

    @property
    def action_space(self) -> Discrete:
        """Return a single action."""
        return Discrete(1)

    def build_observation(
        self, simulation: Simulation, period: Period, request: DecisionRequest | None
    ) -> NDArray[np.float32]:
        """Return the period length."""
        return np.array([period.end_min - period.start_min], dtype=np.float32)

    def apply_action(
        self, simulation: Simulation, request: DecisionRequest, action: np.int64
    ) -> bool:
        """Offer the search."""
        return True

    def compute_reward(self, simulation: Simulation, period: Period) -> float:
        """Return the period length."""
        return period.end_min - period.start_min


@pytest.mark.parametrize("seed", [7, 0])
def test_same_seed_replays_identically(
    make_env: Callable[..., UmosimEnv], seed: int
) -> None:
    """Two environments given one seed produce the same trace, seed zero included."""
    first = run_steps(make_env(AdmissionProblem()), seed, 5)
    second = run_steps(make_env(AdmissionProblem()), seed, 5)

    assert first == second


def test_different_seeds_diverge(make_env: Callable[..., UmosimEnv]) -> None:
    """Two seeds produce two different episodes."""
    env = make_env(AdmissionProblem())

    assert run_steps(env, 7, 5) != run_steps(env, 8, 5)


def test_closing_mid_episode_leaves_the_env_reusable(
    make_env: Callable[..., UmosimEnv],
) -> None:
    """Unwinding a frozen episode does not break the next one."""
    env = make_env(AdmissionProblem())
    env.reset(seed=3)
    env.step(env.action_space.sample())
    env.close()
    assert env.simulation is None

    observation, _ = env.reset(seed=4)

    assert env.simulation is not None
    assert observation in env.observation_space


def test_step_after_termination_is_rejected(make_env: Callable[..., UmosimEnv]) -> None:
    """A problem that ends the episode early leaves nothing to step."""

    class Ending(AdmissionProblem):
        def is_terminated(self, simulation: Simulation) -> bool:
            return True

    env = make_env(Ending())
    env.reset(seed=3)
    _, _, terminated, truncated, _ = env.step(env.action_space.sample())

    assert terminated
    assert not truncated
    with pytest.raises(RuntimeError, match="running episode"):
        env.step(env.action_space.sample())


@pytest.mark.parametrize(
    "action",
    [
        pytest.param(np.int64(2), id="apply_action"),
        pytest.param(np.int64(OFFER), id="compute_reward"),
    ],
)
def test_failed_step_closes_the_episode(
    make_env: Callable[..., UmosimEnv], action: np.int64
) -> None:
    """A step that fails, in the action or in a later problem method, ends the episode.

    Nothing is left frozen or open, and the next step asks for a reset.
    """

    class Failing(AdmissionProblem):
        def compute_reward(self, simulation: Simulation, period: Period) -> float:
            raise ArithmeticError("reward bug")

    env = make_env(Failing())
    env.reset(seed=3)
    with pytest.raises((ValueError, ArithmeticError), match=r"defer|reward bug"):
        env.step(action)

    assert env.simulation is None
    with pytest.raises(RuntimeError, match="running episode"):
        env.step(env.action_space.sample())


def test_simulation_failure_mid_step_closes_the_episode(
    make_env: Callable[..., UmosimEnv], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A simulation that raises after the action reaches the caller and leaves nothing frozen."""
    search = BrokeredAdmissionSearchEngine.search_for_transportation_alternatives
    searches = 0

    def failing_search(
        engine: BrokeredAdmissionSearchEngine, transport_task: TransportRequest
    ) -> TransportationAlternativeBrowser:
        nonlocal searches
        searches += 1
        if searches > 1:
            raise ArithmeticError("search bug")
        return search(engine, transport_task)

    monkeypatch.setattr(
        BrokeredAdmissionSearchEngine,
        "search_for_transportation_alternatives",
        failing_search,
    )
    env = make_env(AdmissionProblem())
    env.reset(seed=3)

    with pytest.raises(ArithmeticError, match="search bug"):
        env.step(env.action_space.sample())

    assert env.simulation is None


def test_episode_runs_to_the_horizon_one_period_per_reward(
    make_env: Callable[..., UmosimEnv],
) -> None:
    """An episode truncates at the horizon, each reward covering one settlement period.

    The warm-up period is rewarded to nobody and info names each period. Periods
    run from one decision point to the next, so their lengths vary. Vehicle holding
    cost accrues per minute, so its cost per period is a direct readout of the
    period length. The dead world takes no further step.
    """
    recorded = Recording()
    env = make_env(recorded)
    _, info = env.reset(seed=7)
    infos = [info]
    while True:
        observation, reward, terminated, truncated, info = env.step(
            env.action_space.sample()
        )
        assert observation in env.observation_space
        assert isinstance(reward, float)
        infos.append(info)
        if terminated or truncated:
            break

    assert truncated
    assert not terminated
    with pytest.raises(RuntimeError, match="running episode"):
        env.step(env.action_space.sample())

    warm_up, *rewarded = recorded.closed
    assert warm_up.start_min == 0

    spans = [(i.start_min, i.end_min) for i in rewarded]
    bounds = [warm_up.end_min, *(end for _, end in spans)]
    assert spans == list(pairwise(bounds))
    assert bounds[-1] == HORIZON

    holding = [i.costs_by_type[CostType.VEHICLE_HOLDING] for i in rewarded]
    per_min = sum(holding) / (HORIZON - warm_up.end_min)
    assert per_min > 0
    assert holding == pytest.approx([per_min * (end - start) for start, end in spans])

    reported = [(info["period_start_min"], info["period_end_min"]) for info in infos]
    assert reported == [(warm_up.start_min, warm_up.end_min), *spans]
    assert [info["profit"] for info in infos[1:]] == [i.profit for i in rewarded]


def test_decider_and_simulation_keep_separate_global_random_streams(
    make_env: Callable[..., UmosimEnv], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Global draws inside the simulation and in the decider never touch each other.

    Every decision point draws once from inside the simulation greenlet to stand in
    for a component drawing global randomness mid-episode.
    """
    simulation_draws: list[tuple[float, float]] = []
    decide = DecisionChannel.decide

    def drawing_decide(
        channel: DecisionChannel, requester_id: SimId, payload: object = None
    ) -> object:
        simulation_draws.append((random.random(), np.random.random()))
        return decide(channel, requester_id, payload)

    monkeypatch.setattr(DecisionChannel, "decide", drawing_decide)

    def run(is_decider_drawing: bool) -> tuple[list[tuple[float, float]], float]:
        simulation_draws.clear()
        env = make_env(AdmissionProblem())
        random.seed(1)
        env.reset(seed=7)
        for _ in range(3):
            if is_decider_drawing:
                random.random()
            env.step(env.action_space.sample())
        env.close()
        return list(simulation_draws), random.random()

    quiet_simulation, quiet_decider = run(is_decider_drawing=False)
    busy_simulation, _ = run(is_decider_drawing=True)

    random.seed(1)
    assert quiet_decider == random.random()
    assert busy_simulation == quiet_simulation


def test_problem_without_an_operator_runs_on_period_bounds(
    make_env: Callable[..., UmosimEnv],
) -> None:
    """A plain Problem needs no operator, its periods tile the episode after the warm-up."""
    env = make_env(Stopwatch())
    _, info = env.reset(seed=7)
    warm_up_end = info["period_end_min"]
    rewards = []
    while True:
        _, reward, terminated, truncated, info = env.step(0)
        assert reward == info["period_end_min"] - info["period_start_min"]
        rewards.append(reward)
        if terminated or truncated:
            break

    assert sum(rewards) == pytest.approx(HORIZON - warm_up_end)


def test_gymnasium_make_builds_the_registered_environment(
    admission_project: Path,
) -> None:
    """The module-qualified id builds a working environment with the standard wrappers."""
    env = gymnasium.make(
        f"rl.env:{ENV_ID}",
        project_dir=admission_project,
        problem=AdmissionProblem(),
        horizon_min=HORIZON,
    )
    try:
        observation, _ = env.reset(seed=3)
        env.step(env.action_space.sample())
    finally:
        env.close()

    assert observation in env.observation_space


@pytest.mark.skipif(not os.path.isdir("/dev/fd"), reason="needs /dev/fd to count files")
def test_resets_do_not_accumulate_open_files(
    make_env: Callable[..., UmosimEnv],
) -> None:
    """Every episode closes its log files, so a training loop cannot hit EMFILE."""
    env = make_env(AdmissionProblem())
    env.reset(seed=1)
    env.step(env.action_space.sample())
    env.close()
    baseline = len(os.listdir("/dev/fd"))

    for seed in range(2, 5):
        env.reset(seed=seed)
        env.step(env.action_space.sample())
        env.close()

    assert len(os.listdir("/dev/fd")) == baseline
