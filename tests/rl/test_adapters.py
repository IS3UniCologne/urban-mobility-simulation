"""Unit tests for the seam adapters."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from rl.adapters import BrokeredAdmissionSearchEngine, Search
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)
from simulation.operator.ride_hailing_fleet import RideHailingFleet
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.operator.search_engine import SearchEngineDependencies

pytestmark = pytest.mark.unit

TRANSPORT_REQUEST = Mock(name="transport_request")


def make_search_engine(
    reply: object = None, has_broker: bool = True
) -> tuple[BrokeredAdmissionSearchEngine, Mock]:
    """Build a brokered search engine over mocks and return it with its broker."""
    sim = Mock()
    sim.uid_manager.generate_uid.return_value = (1, "BrokeredAdmissionSearchEngine_1")
    if has_broker:
        sim.decision_broker.decide.return_value = reply
    else:
        sim.decision_broker = None
    operator = Mock()
    operator.fleet = Mock(spec=RideHailingFleet)
    deps = SearchEngineDependencies(sim=sim, config=Mock(), operator=operator)
    return BrokeredAdmissionSearchEngine(deps), sim.decision_broker


def search(
    engine: BrokeredAdmissionSearchEngine, found: list[object]
) -> TransportationAlternativeBrowser:
    """Run one search whose plain part finds ``found`` and return what the engine returns."""
    browser = TransportationAlternativeBrowser()
    browser.transportation_alternatives = list(found)
    with patch.object(
        RideHailingSearchEngine,
        "search_for_transportation_alternatives",
        return_value=browser,
    ):
        return engine.search_for_transportation_alternatives(TRANSPORT_REQUEST)


@pytest.mark.parametrize(("reply", "is_offered"), [(True, True), (False, False)])
def test_reply_decides_whether_the_alternatives_are_offered(
    reply: bool, is_offered: bool
) -> None:
    """True offers every alternative found, False defers and offers none.

    The decision carries the request and the alternatives, whatever the reply.
    """
    engine, broker = make_search_engine(reply=reply)
    found = [Mock(name="alternative_1"), Mock(name="alternative_2")]

    offered = search(engine, found)

    assert offered.transportation_alternatives == (found if is_offered else [])
    broker.decide.assert_called_once_with(
        engine.operator.uid, Search(TRANSPORT_REQUEST, tuple(found))
    )


@pytest.mark.parametrize("reply", ["yes", 1, 1.0, None])
def test_reply_that_is_no_bool_is_rejected(reply: object) -> None:
    """A reply other than True or False fails the search it answers."""
    engine, _ = make_search_engine(reply=reply)

    with pytest.raises(TypeError, match="offer"):
        search(engine, [Mock(name="alternative_1")])


def test_search_that_finds_nothing_asks_nobody() -> None:
    """Without alternatives there is nothing to decide, so no decision point opens."""
    engine, broker = make_search_engine(reply=False)

    offered = search(engine, [])

    assert offered.transportation_alternatives == []
    broker.decide.assert_not_called()


def test_search_still_offers_without_a_broker() -> None:
    """Without a broker the adapter offers every request the vehicles it finds."""
    engine, _ = make_search_engine(has_broker=False)
    found = [Mock(name="alternative_1")]

    assert search(engine, found).transportation_alternatives == found
