"""Gymnasium environment for the simulation.

``UmosimEnv`` runs one simulation project as a ``gymnasium.Env``.
The seam adapter of the project asks the decision broker at each decision point.
The ``Problem`` turns these decisions into observations, actions and rewards.
The environment is registered under ``ENV_ID``, so ``gymnasium.make`` can build one too.
"""

from __future__ import annotations

import random
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import gymnasium as gym
import numpy as np

from rl.channel import DecisionChannel
from rl.problem import ActT, ObsT, Period
from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from rl.channel import DecisionRequest
    from rl.problem import Problem

MAX_SEED = 2**32

ENV_ID = "Umosim-v0"
"""Gymnasium id of ``UmosimEnv``, e.g. ``gymnasium.make("rl.env:Umosim-v0", ...)``."""


class _GlobalRandomState:
    """
    A saved copy of the states of the global ``random`` and ``numpy.random`` generators.

    The simulation seeds both global generators.
    Without a copy per episode, two environments in one process would share one random stream.
    The copy is taken on construction.
    ``active`` is a context manager: the body of its ``with`` statement runs on the copy.
    """

    __slots__ = ("_numpy", "_python")

    def __init__(self) -> None:
        self._capture()

    def restore(self) -> None:
        """Restore the global generator states."""
        random.setstate(self._python)
        np.random.set_state(self._numpy)

    @contextmanager
    def active(self) -> Generator[None]:
        """Run the ``with`` body on these states, keep its final states and restore the caller's."""
        caller = _GlobalRandomState()
        self.restore()
        try:
            yield
        finally:
            self._capture()
            caller.restore()

    def _capture(self) -> None:
        """Take the current states of the global generators."""
        self._python = random.getstate()
        self._numpy = np.random.get_state()


@dataclass(slots=True)
class _RunningEpisode:
    """
    One running episode with everything ``step`` and ``close`` need.

    ``request`` is the decision the simulation waits at.
    It is None when the episode takes no further step.
    ``period_start_min`` is the simulation time the open period started (min).
    """

    channel: DecisionChannel
    simulation: Simulation
    randomness: _GlobalRandomState
    request: DecisionRequest | None
    period_start_min: float


class UmosimEnv(gym.Env[ObsT, ActT]):
    """
    Gymnasium ``Env`` for one simulation project, one episode at a time.

    ``reset`` builds a fresh ``Simulation`` from the project and runs it to its first decision point.
    ``step`` answers that decision with the action and runs on to the next one.
    An episode ends at the horizon, or earlier when the problem terminates it.

    Parameters
    ----------
    project_dir : str or Path
        Project directory with ``config.toml`` and the config-as-code modules.
    problem : Problem
        Problem whose spaces, observations, actions and rewards the environment exposes.
    horizon_min : int or None
        Simulation time each episode runs to (min). None uses the configured ``END_TIME``.

    Examples
    --------
    >>> env = UmosimEnv("data/projects/ridehailing_admission_demo", AdmissionProblem(), horizon_min=1440)
    >>> observation, info = env.reset(seed=1)
    >>> observation, reward, terminated, truncated, info = env.step(env.action_space.sample())
    >>> env.close()

    ``gymnasium.make`` builds the same environment from ``ENV_ID`` and adds the standard Gymnasium wrappers.

    >>> env = gymnasium.make(
    ...     "rl.env:Umosim-v0",
    ...     project_dir="data/projects/ridehailing_admission_demo",
    ...     problem=AdmissionProblem(),
    ...     horizon_min=1440,
    ... )
    """

    def __init__(
        self,
        project_dir: str | Path,
        problem: Problem[ObsT, ActT],
        horizon_min: int | None = None,
    ) -> None:
        super().__init__()
        self._config = Configuration(str(project_dir))
        self._problem = problem
        self.observation_space = self._problem.observation_space
        self.action_space = self._problem.action_space

        self._horizon_min = horizon_min
        self._running: _RunningEpisode | None = None

    @property
    def problem(self) -> Problem[ObsT, ActT]:
        """Return the problem whose spaces, observations, actions and rewards the environment exposes."""
        return self._problem

    @property
    def simulation(self) -> Simulation | None:
        """Return the simulation of the running episode, or None when no episode runs."""
        return self._running.simulation if self._running is not None else None

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[ObsT, dict[str, Any]]:
        """Start a fresh episode and run it to its first decision point.

        Parameters
        ----------
        seed : int or None
            Seed the episode seeds are drawn from, equal seeds give equal episodes.
        options : dict or None
            Unused.

        Returns
        -------
        tuple
            First observation and info.

        Raises
        ------
        RuntimeError
            If the simulation reached the horizon without asking for a decision.
        """
        super().reset(seed=seed)
        self.close()

        episode_seed = int(self.np_random.integers(1, MAX_SEED))
        channel = DecisionChannel()
        randomness = _GlobalRandomState()
        with randomness.active():
            simulation = Simulation(
                self._config, decision_broker=channel, seed=episode_seed
            )
            try:
                start_min = simulation.sim.time
                running = _RunningEpisode(
                    channel=channel,
                    simulation=simulation,
                    randomness=randomness,
                    request=self._start(simulation, channel),
                    period_start_min=start_min,
                )
                warm_up = self._close_period(running)
                observation = self._problem.build_observation(
                    simulation, warm_up, running.request
                )
                info = self._info(simulation, warm_up)
            except BaseException:
                _teardown(simulation, channel)
                raise

        self._running = running
        return observation, info

    def step(self, action: ActT) -> tuple[ObsT, float, bool, bool, dict[str, Any]]:
        """Apply an action and run on to the next decision point or the horizon.

        Step size is not a fixed time interval.

        Parameters
        ----------
        action : ActT
            Action drawn from ``action_space``.

        Returns
        -------
        tuple
            Observation, reward, terminated, truncated and info. The info holds the
            problem's entries plus ``period_start_min`` and ``period_end_min`` of the
            settled period.

        Raises
        ------
        RuntimeError
            If no episode runs or the last one has ended. A step that fails for
            any reason ends the episode, so the exception it raises is the last
            word on it.
        """
        running = self._running
        if running is None or running.request is None:
            msg = "step() needs a running episode, call reset() first."
            raise RuntimeError(msg)

        problem = self._problem
        simulation = running.simulation
        with running.randomness.active():
            try:
                reply = problem.apply_action(simulation, running.request, action)
                request = self._accept(simulation, running.channel.resume(reply))
                period = self._close_period(running)
                reward = problem.compute_reward(simulation, period)
                terminated = problem.is_terminated(simulation)
                observation = problem.build_observation(simulation, period, request)
                info = self._info(simulation, period)
            except BaseException:
                self._running = None
                _teardown(simulation, running.channel)
                raise

        running.request = None if terminated else request
        truncated = request is None and not terminated
        return observation, reward, terminated, truncated, info

    def close(self) -> None:
        """Unwind the running episode if there is one and release its log handlers."""
        running, self._running = self._running, None
        if running is not None:
            with running.randomness.active():
                _teardown(running.simulation, running.channel)

    def _start(
        self, simulation: Simulation, channel: DecisionChannel
    ) -> DecisionRequest:
        """Start the problem's episode on the built world and return its first decision."""
        self._problem.on_episode_start(simulation)
        horizon_min = self._horizon_min
        request = self._accept(
            simulation,
            channel.start(lambda: simulation.run_simulation(end_time=horizon_min)),
        )
        if request is None:
            msg = (
                "Simulation reached the horizon without asking for a decision. "
                "Check that the configuration selects a seam adapter that asks "
                "for a decision before the horizon."
            )
            raise RuntimeError(msg)
        return request

    def _accept(
        self, simulation: Simulation, request: DecisionRequest | None
    ) -> DecisionRequest | None:
        """Let the problem check a decision the simulation asked for, none at the horizon."""
        if request is not None:
            self._problem.on_request(simulation, request)
        return request

    def _close_period(self, running: _RunningEpisode) -> Period:
        """Close the open period at the current simulation time and open the next one."""
        period = Period(running.period_start_min, running.simulation.sim.time)
        running.period_start_min = period.end_min
        self._problem.close_period(running.simulation, period)
        return period

    def _info(self, simulation: Simulation, period: Period) -> dict[str, Any]:
        """Return the problem's diagnostics and the bounds of the settled period."""
        return {
            **self._problem.info(simulation, period),
            "period_start_min": period.start_min,
            "period_end_min": period.end_min,
        }


def _teardown(simulation: Simulation, channel: DecisionChannel) -> None:
    """Mark the simulation ended, kill its greenlet and release its log handlers.

    Garbage collection finalizes abandoned simulation processes later.
    Their ``finally`` blocks touch resources only while the phase is ``RUNNING``.
    The simulation is marked ended first, so they do not touch a world that is gone.
    """
    simulation.sim.mark_ended()
    try:
        channel.close()
    finally:
        simulation.close()


gym.register(id=ENV_ID, entry_point="rl.env:UmosimEnv")
