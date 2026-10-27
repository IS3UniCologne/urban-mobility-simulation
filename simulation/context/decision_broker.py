"""Protocol between simulation decision points and an external decider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from simulation.helper.types import SimId


class DecisionBroker(Protocol):
    """
    Protocol through which a decision point asks an external decider.

    A seam adapter reads the broker from ``SimulationContext.decision_broker`` and calls ``decide`` where a heuristic decided before.
    None there means no decider is attached.
    Implementations live outside the simulation core, in the ``rl`` package.
    """

    def decide(self, requester_id: SimId, payload: object = None) -> object:
        """Request a decision, blocking until the decider replies.

        Callable from synchronous code or a SimPy process, at any stack depth.

        Parameters
        ----------
        requester_id : SimId
            Entity requesting the decision.
        payload : object
            Local facts only the decision point has, opaque to the core. None
            when the decider needs no extra facts to act.

        Returns
        -------
        object
            Reply from the decider, opaque to the core. The seam adapter defines
            the replies it accepts.
        """
        ...
