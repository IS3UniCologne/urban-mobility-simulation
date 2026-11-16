"""Base class for problems and the data its methods receive.

``Problem`` defines what a learning agent observes, what its actions mean and how it is rewarded.
``UmosimEnv`` calls its methods with the running ``Simulation`` of the episode.
At each decision point ``on_request`` checks the ``DecisionRequest`` the other methods receive.
``close_period`` hands the problem the ``Period`` since the previous decision point.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from gymnasium.spaces import Space

    from rl.channel import DecisionRequest
    from simulation.simulation import Simulation

ObsT = TypeVar("ObsT")
"""Observation type, the element type of ``observation_space``."""

ActT = TypeVar("ActT")
"""Action type, the element type of ``action_space``."""


@dataclass(frozen=True, slots=True)
class Period:
    """
    Bounds of one settlement period, the span between two decision points.

    Attributes
    ----------
    start_min : float
        Simulation time the period opened (min).
    end_min : float
        Simulation time the period closed (min).
    """

    start_min: float
    end_min: float


class Problem(ABC, Generic[ObsT, ActT]):
    """
    ABC for one reinforcement learning problem: observation, action and reward.

    Subclass it to define what the learning agent sees and does at each decision point.
    The seam adapter decides when the simulation asks. The problem only answers.

    ``UmosimEnv`` calls ``on_episode_start`` when an episode starts.
    Each time the simulation asks for a decision it calls ``on_request`` once, so the other methods can trust the request.
    At the first decision point it then calls ``close_period`` for the warm-up, ``build_observation`` and ``info``.
    Each step calls ``apply_action``, runs the simulation on to the next decision point, calls ``on_request`` for it, then ``close_period``, ``compute_reward``, ``is_terminated``, ``build_observation`` and ``info``.
    Every call after ``on_episode_start`` happens while the simulation is frozen at a decision point or has reached the horizon.

    The spaces are read once before the first episode, so they must not change after construction.
    """

    @property
    @abstractmethod
    def observation_space(self) -> Space[ObsT]:
        """Gymnasium space every built observation lies in."""

    @property
    @abstractmethod
    def action_space(self) -> Space[ActT]:
        """Gymnasium space actions are drawn from."""

    def on_episode_start(self, simulation: Simulation) -> None:
        """Reset per-episode state on the fresh world, before the simulation runs.

        Take any starting values that ``close_period`` compares against here.
        Raise here to reject a configuration before simulation time passes.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode, built but not yet run.
        """

    def on_request(self, simulation: Simulation, request: DecisionRequest) -> None:
        """Check a decision the simulation asked for.

        ``UmosimEnv`` calls it once per decision, before ``build_observation`` and ``apply_action`` receive the request.
        Raise to reject a decision the problem cannot answer, such as one from another seam.
        The default accepts every request.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode, frozen at the decision point.
        request : DecisionRequest
            Decision the simulation waits for.
        """

    def close_period(self, simulation: Simulation, period: Period) -> None:
        """Take what the problem needs from the period that ends at the current decision point or at the horizon.

        ``UmosimEnv`` calls it once per period, before ``build_observation``, ``compute_reward`` and ``info`` receive the same bounds.
        The default takes nothing.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period, from the previous decision point or from episode start to the current simulation time.
        """

    @abstractmethod
    def build_observation(
        self, simulation: Simulation, period: Period, request: DecisionRequest | None
    ) -> ObsT:
        """Build the observation for the decision point the simulation is frozen at.

        It must not change any state.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period, from the previous decision point or from episode start.
        request : DecisionRequest or None
            Pending decision. None at the horizon. A terminated step still receives the decision it stopped at.
        """

    @abstractmethod
    def apply_action(
        self, simulation: Simulation, request: DecisionRequest, action: ActT
    ) -> object:
        """Turn an action into the reply for the frozen ``decide`` call.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        request : DecisionRequest
            Decision the action answers.
        action : ActT
            Action drawn from ``action_space``.

        Returns
        -------
        object
            Reply for the waiting ``decide`` call. The seam adapter defines the
            replies it accepts.
        """

    @abstractmethod
    def compute_reward(self, simulation: Simulation, period: Period) -> float:
        """Return the reward for the period that just closed.

        The period runs from the decision point the action answered to the next one, or to the horizon.
        Scale rewards with a Gymnasium wrapper such as ``TransformReward``, not here.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period.
        """

    def is_terminated(self, simulation: Simulation) -> bool:
        """Return whether the episode ended on the problem's own terms.

        Reaching the horizon is truncation, so the default is False.
        A terminated episode takes no further step.
        An episode terminated before the horizon skips the post-processing of the simulation.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        """
        return False

    def info(self, simulation: Simulation, period: Period) -> dict[str, Any]:
        """Return diagnostics for the current step.

        ``UmosimEnv`` adds ``period_start_min`` and ``period_end_min``, which replace
        entries of the same name.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period.
        """
        return {}
