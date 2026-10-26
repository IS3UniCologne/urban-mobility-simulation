"""Unit tests for DecisionChannel."""

import pytest

pytest.importorskip("greenlet")

from rl.channel import DecisionChannel, DecisionRequest, EpisodeFinishedError
from simulation.helper.types import SimId

pytestmark = pytest.mark.unit

REQUESTER = SimId("Operator_1")


def test_decide_from_nested_sync_frames() -> None:
    """A decision point freezes the simulation from deep inside a synchronous stack."""
    channel = DecisionChannel()
    received: list[object] = []

    def deep(depth: int) -> object:
        if depth:
            return deep(depth - 1)
        return channel.decide(REQUESTER, {"depth": depth})

    def run() -> None:
        received.append(deep(5))
        received.append(deep(5))

    assert channel.start(run) == DecisionRequest(REQUESTER, {"depth": 0})
    assert channel.resume("first") == DecisionRequest(REQUESTER, {"depth": 0})
    assert not channel.finished

    assert channel.resume("second") is None
    assert channel.finished
    assert received == ["first", "second"]


def test_run_completing_without_decisions() -> None:
    """A run that never decides finishes at once with no request."""
    channel = DecisionChannel()

    assert channel.start(lambda: None) is None
    assert channel.finished


def test_exception_propagates_across_switch() -> None:
    """A failure on the simulation side reaches the decider."""
    channel = DecisionChannel()

    def run() -> None:
        channel.decide(REQUESTER)
        raise ValueError("boom")

    channel.start(run)
    with pytest.raises(ValueError, match="boom"):
        channel.resume(None)
    assert channel.finished


def test_close_unwinds_and_runs_finally() -> None:
    """Closing a frozen episode runs its finally blocks once, closing again is a no-op."""
    channel = DecisionChannel()
    cleaned: list[bool] = []

    def run() -> None:
        try:
            while True:
                channel.decide(REQUESTER)
        finally:
            cleaned.append(True)

    channel.start(run)
    assert not channel.finished

    channel.close()
    channel.close()
    assert cleaned == [True]
    assert channel.finished


def test_close_kills_a_decision_requested_while_unwinding() -> None:
    """A decision point reached during the unwind is killed too, never left frozen."""
    channel = DecisionChannel()
    unwound: list[bool] = []

    def run() -> None:
        try:
            channel.decide(REQUESTER)
        finally:
            channel.decide(REQUESTER)
            unwound.append(True)

    channel.start(run)
    channel.close()

    assert channel.finished
    assert unwound == []


def test_resume_after_finish_raises() -> None:
    """Resuming a finished episode raises instead of silently doing nothing."""
    channel = DecisionChannel()
    channel.start(lambda: None)

    with pytest.raises(EpisodeFinishedError):
        channel.resume(None)


def test_decide_outside_episode_raises() -> None:
    """A decision point on a channel that was never started raises."""
    channel = DecisionChannel()

    with pytest.raises(EpisodeFinishedError):
        channel.decide(REQUESTER)
