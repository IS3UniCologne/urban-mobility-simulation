"""Base class for problems whose learning agent acts for one operator.

``OperatorProblem`` picks the operator when an episode starts and settles its revenue and cost per period.
``settlement`` holds the ``SettlementPeriod`` of the period that closed last.
The default reward is its profit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rl.bookkeeper import Bookkeeper
from rl.problem import ActT, ObsT, Problem

if TYPE_CHECKING:
    from rl.bookkeeper import SettlementPeriod
    from rl.channel import DecisionRequest
    from rl.problem import Period
    from simulation.operator.operator import Operator
    from simulation.simulation import Simulation
    from simulation.world.world import World


class OperatorProblem(Problem[ObsT, ActT]):
    """
    ABC for a problem whose learning agent acts for one operator.

    ``on_episode_start`` picks the operator through ``select_operator``.
    ``operator`` returns it until the next episode starts.
    An override of ``on_episode_start`` calls ``super().on_episode_start(simulation)`` first.
    ``close_period`` settles the revenue and cost of that operator into ``settlement``.
    The default reward is the profit of the settlement.
    ``on_request`` rejects a decision another operator asked for.
    ``info`` reports the revenue, cost, profit and fulfilled trips of the settlement.
    """

    def __init__(self) -> None:
        self._bookkeeper: Bookkeeper | None = None

    @property
    def operator(self) -> Operator:
        """Return the operator the learning agent acts for in the current episode."""
        return self._books.operator

    @property
    def settlement(self) -> SettlementPeriod:
        """Return the revenue, cost per type and log entries of the period that closed last."""
        return self._books.settlement

    @property
    def _books(self) -> Bookkeeper:
        """Return the bookkeeper of the current episode, or raise before one starts."""
        if self._bookkeeper is None:
            msg = (
                "No operator is picked. Call reset() first. An override of "
                "on_episode_start() calls super().on_episode_start() first."
            )
            raise RuntimeError(msg)
        return self._bookkeeper

    def select_operator(self, world: World) -> Operator:
        """Pick the operator the learning agent acts for.

        Parameters
        ----------
        world : World
            Populated world of the episode about to start.

        Returns
        -------
        Operator
            Operator the learning agent acts for. Its revenue and cost are settled
            per period.

        Raises
        ------
        ValueError
            If the world has no operator or more than one.
        """
        operators = world.operators
        if len(operators) != 1:
            msg = (
                f"Expected exactly one operator for the learning agent to act for, "
                f"found {len(operators)}. Override select_operator() to pick one."
            )
            raise ValueError(msg)
        return operators[0]

    def on_episode_start(self, simulation: Simulation) -> None:
        """Pick the operator and start to settle its revenue and cost.

        Revenue, cost and log entries booked before this call belong to no period.
        An override calls ``super().on_episode_start(simulation)`` first, since
        ``operator`` is unset until then.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode, built but not yet run.

        Raises
        ------
        ValueError
            If ``select_operator`` finds no single operator to act for.
        """
        self._bookkeeper = Bookkeeper(self.select_operator(simulation.world))

    def on_request(self, simulation: Simulation, request: DecisionRequest) -> None:
        """Raise unless the operator the learning agent acts for asked for the decision.

        The decision broker is shared by the whole world.
        A second operator with a brokered seam adapter sends its decisions to the same channel.
        This problem observes and settles only its own operator, so it cannot answer them.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode, frozen at the decision point.
        request : DecisionRequest
            Decision the simulation waits for.

        Raises
        ------
        ValueError
            If ``request.requester_id`` is not the uid of ``operator``.
        """
        if request.requester_id != self.operator.uid:
            msg = (
                f"{request.requester_id} asked for the decision, but the learning "
                f"agent acts for {self.operator.uid}. Give only that operator a seam "
                "adapter that asks the decision broker."
            )
            raise ValueError(msg)

    def close_period(self, simulation: Simulation, period: Period) -> None:
        """Settle the revenue and cost of the operator over the period into ``settlement``.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period, from the previous decision point or from episode start.

        Raises
        ------
        RuntimeError
            If ``on_episode_start`` of this class did not run first.
        """
        self._books.settle(period)

    def compute_reward(self, simulation: Simulation, period: Period) -> float:
        """Return the reward for the period that just closed, the profit of its settlement by default.

        The period runs from the decision point the action answered to the next one, or to the horizon.
        Scale rewards with a Gymnasium wrapper such as ``TransformReward``, not here.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period, the bounds of ``settlement``.
        """
        return self.settlement.profit

    def info(self, simulation: Simulation, period: Period) -> dict[str, Any]:
        """Return the revenue, cost, profit and fulfilled trips of the settlement.

        Summed over the steps of an episode, ``profit`` is the profit of the operator after the first decision point, whatever the reward pays.

        Parameters
        ----------
        simulation : Simulation
            Simulation of the episode.
        period : Period
            Closed period, the bounds of ``settlement``.
        """
        settlement = self.settlement
        return {
            "revenue": settlement.revenue,
            "cost": settlement.cost,
            "profit": settlement.profit,
            "fulfilled": settlement.fulfilled,
        }
