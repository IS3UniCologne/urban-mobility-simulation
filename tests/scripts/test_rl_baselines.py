"""Unit tests for the baselines of the shipped problems."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

pytest.importorskip("gymnasium")

from gymnasium.spaces import Discrete

from rl.problems import AdmissionProblem
from rl.problems.admission import DEFER, OFFER
from rl.problems.admission import FEATURES as ADMISSION_FEATURES
from scripts.rl_baselines import (
    ADMISSION_BASELINES,
    always,
    deadhead,
    nearby,
    nearby_when_busy,
    run_episode,
)
from tests.rl.fakes import make_lost, make_served, make_simulation

if TYPE_CHECKING:
    from numpy.typing import NDArray

pytestmark = pytest.mark.unit


def admission_observation(
    standby: float = 0.0, pickup: float = 0.0, trip: float = 0.0
) -> NDArray[np.float32]:
    """Build an admission observation with the given standby, pickup and trip entries."""
    observation = np.zeros(len(ADMISSION_FEATURES), dtype=np.float32)
    observation[ADMISSION_FEATURES.index("standby")] = standby
    observation[ADMISSION_FEATURES.index("pickup")] = pickup
    observation[ADMISSION_FEATURES.index("trip")] = trip
    return observation


@pytest.mark.parametrize("name", list(ADMISSION_BASELINES))
def test_every_baseline_returns_an_action_in_the_space(name: str) -> None:
    """Each named baseline answers an observation with an action the problem accepts."""
    policy = ADMISSION_BASELINES[name]
    if policy is None:
        pytest.skip("samples the action space")
    problem = AdmissionProblem()
    observation = np.zeros(problem.observation_space.shape, dtype=np.float32)

    assert policy(observation) in problem.action_space


@pytest.mark.parametrize(
    ("pickup", "action"), [(0.0, OFFER), (0.3, OFFER), (0.31, DEFER)]
)
def test_nearby_policy_offers_short_pickup_legs_only(
    pickup: float, action: int
) -> None:
    """The pickup entry alone decides, up to and including the nearby share."""
    assert nearby(admission_observation(pickup=pickup)) == action


@pytest.mark.parametrize(
    ("standby", "pickup", "action"),
    [(0.5, 0.9, OFFER), (0.1, 0.9, OFFER), (0.05, 0.9, DEFER), (0.05, 0.1, OFFER)],
)
def test_busy_aware_policy_offers_everything_while_vehicles_stand_by(
    standby: float, pickup: float, action: int
) -> None:
    """Idle vehicles take any search, a busy fleet takes nearby ones only."""
    assert nearby_when_busy(admission_observation(standby, pickup)) == action


@pytest.mark.parametrize(
    ("pickup", "trip", "action"),
    [
        (0.0, 0.0, OFFER),
        (0.1, 0.5, OFFER),
        (1.0, 0.5, OFFER),
        (0.3, 0.2, DEFER),
        (0.9, 1.0, OFFER),
    ],
)
def test_deadhead_policy_offers_pickup_legs_up_to_the_trip(
    pickup: float, trip: float, action: int
) -> None:
    """The trip entry is read back to the pickup scale, a full entry beats any leg."""
    assert deadhead(admission_observation(pickup=pickup, trip=trip)) == action


def settled(profit: float, fulfilled: int = 0) -> dict[str, float | int]:
    """Build the info of one step as an operator problem reports it."""
    return {"profit": profit, "fulfilled": fulfilled}


class FakeEnv:
    """Env stub replaying fixed infos with zero rewards, truncating after the last one.

    The user log of its simulation holds the served users with their waits and the lost ones.
    """

    def __init__(
        self,
        infos: list[dict[str, float | int]],
        waits: tuple[float, ...] = (),
        lost: int = 0,
    ) -> None:
        self.action_space = Discrete(2)
        self.infos = list(infos)
        self.actions: list[int] = []
        self.problem = AdmissionProblem()
        self.simulation = make_simulation([])
        user_log = self.simulation.world.user_log
        for wait in waits:
            user_log.log_trip_outcome(make_served(wait))
        for _ in range(lost):
            user_log.log_trip_outcome(make_lost())

    def reset(self, *, seed: int) -> tuple[NDArray[np.float32], dict]:
        """Return a zero observation."""
        return np.zeros(1, dtype=np.float32), {}

    def step(self, action: int) -> tuple:
        """Pop the next info, truncating on the last."""
        self.actions.append(int(action))
        info = self.infos.pop(0)
        return np.zeros(1, dtype=np.float32), 0.0, False, not self.infos, info


def test_episode_outcome_reads_the_infos_and_the_user_log_not_the_rewards() -> None:
    """Profit and fulfilled trips are summed from the infos, lost users and waits come from the user log's statistics."""
    env = FakeEnv(
        [settled(1.0, 1), settled(2.5, 2), settled(-0.5)], waits=(4.0, 8.0), lost=1
    )

    outcome = run_episode(env, always(OFFER), seed=3)  # type: ignore[arg-type]

    assert outcome.profit == pytest.approx(3.0)
    assert outcome.fulfilled == 3
    assert outcome.lost == 1
    assert outcome.wait_min == pytest.approx(6.0)
    assert env.actions == [OFFER, OFFER, OFFER]


def test_random_policy_samples_the_action_space_reproducibly() -> None:
    """Without a policy the actions come from the seeded action space."""
    first = FakeEnv([settled(0.0), settled(0.0)])
    second = FakeEnv([settled(0.0), settled(0.0)])

    run_episode(first, None, seed=3)  # type: ignore[arg-type]
    run_episode(second, None, seed=3)  # type: ignore[arg-type]

    assert first.actions == second.actions
    assert set(first.actions) <= {DEFER, OFFER}
