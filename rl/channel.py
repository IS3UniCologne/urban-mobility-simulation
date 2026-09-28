"""A DecisionBroker that runs on greenlets.

There are two greenlets.
The simulation greenlet runs the simulation, ``start`` creates it.
The decider greenlet is the one that called ``start``, in the ``rl`` package that is ``UmosimEnv``.

``decide`` switches from the simulation greenlet to the decider greenlet with a ``DecisionRequest``.
``resume`` switches back with the reply, which ``decide`` then returns.
The switch freezes every call in progress.
A decision point can therefore call ``decide`` from any depth, in synchronous code or in a SimPy process.
The functions that lead to the decision point need no new parameters.
Only one of the two greenlets runs at a time, so seeded runs stay deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from greenlet import greenlet

if TYPE_CHECKING:
    from collections.abc import Callable

    from simulation.helper.types import SimId


class EpisodeFinishedError(RuntimeError):
    """Raised when a DecisionChannel is used outside a running episode."""


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    """
    A decision that waits for the decider.

    Attributes
    ----------
    requester_id : SimId
        Entity asking for the decision.
    payload : object
        Local facts of the decision point. None when the decider needs no extra
        facts to act.
    """

    requester_id: SimId
    payload: object = None


class DecisionChannel:
    """
    A DecisionBroker using greenlets that stops the simulation inside ``decide`` until the decider replies.

    Call ``start`` with the function that runs the simulation.
    It returns the first ``DecisionRequest``.
    ``resume`` answers it and returns the next one, or None when the simulation has finished.
    ``close`` kills a simulation that still waits mid-episode.

    ``start``, ``resume`` and ``close`` must run in the greenlet that called ``start``.
    A finished simulation greenlet switches back to its parent.

    Examples
    --------
    >>> channel = DecisionChannel()
    >>> request = channel.start(lambda: simulation.run_simulation())
    >>> while request is not None:
    ...     request = channel.resume(reply_for(request))
    """

    __slots__ = ("_decider", "_sim")

    def __init__(self) -> None:
        self._decider: greenlet | None = None
        self._sim: greenlet | None = None

    @property
    def finished(self) -> bool:
        """Return whether the simulation greenlet is dead or was never started."""
        return self._sim is None or self._sim.dead

    def decide(self, requester_id: SimId, payload: object = None) -> object:
        """Ask the decider for a decision and freeze the simulation until it replies.

        Parameters
        ----------
        requester_id : SimId
            Entity asking for the decision.
        payload : object
            Local facts of the decision point. None when the decider needs no
            extra facts to act.

        Returns
        -------
        object
            Reply from the decider.

        Raises
        ------
        EpisodeFinishedError
            If no episode is running.
        """
        if self._decider is None or self.finished:
            raise EpisodeFinishedError(
                "decide() called outside a running episode. "
                "Start the channel before running the simulation."
            )
        return self._decider.switch(DecisionRequest(requester_id, payload))

    def start(self, run: Callable[[], None]) -> DecisionRequest | None:
        """Run ``run`` in a fresh simulation greenlet up to its first decision point.

        Parameters
        ----------
        run : callable
            Zero-argument callable running the whole simulation (e.g. ``lambda: simulation.run_simulation()``).

        Returns
        -------
        DecisionRequest or None
            First decision requested. None when the simulation finished without one.
        """
        self._decider = greenlet.getcurrent()
        self._sim = greenlet(run)
        return self._run_to_next_decision(self._sim)

    def resume(self, reply: object = None) -> DecisionRequest | None:
        """Answer the frozen decision point and run on to the next one.

        Parameters
        ----------
        reply : object
            Value the pending ``decide`` call returns.

        Returns
        -------
        DecisionRequest or None
            Next decision requested. None when the simulation finished.

        Raises
        ------
        EpisodeFinishedError
            If the episode already finished.
        """
        if self._sim is None or self.finished:
            raise EpisodeFinishedError("resume() called after the episode finished.")
        return self._run_to_next_decision(self._sim, reply)

    def close(self) -> None:
        """Kill the simulation greenlet if it is still frozen at a decision point.

        The frozen ``decide`` call raises ``GreenletExit``, so the ``finally`` blocks of the simulation run.
        SimPy first finishes the events queued at the same instant.
        A decision one of them requests is killed the same way.
        """
        sim = self._sim
        if sim is None:
            return
        while not sim.dead:
            sim.throw()
        self._sim = None

    @staticmethod
    def _run_to_next_decision(sim: greenlet, *args: object) -> DecisionRequest | None:
        """Switch into the simulation and return the request it froze at.

        A dead greenlet returns the result of ``run`` instead of a request.
        The greenlet state decides, not the value.
        """
        request = sim.switch(*args)
        return None if sim.dead else request
