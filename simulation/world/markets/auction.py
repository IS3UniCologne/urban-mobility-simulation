"""Generic auction base class for markets."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar

from beartype.door import die_if_unbearable  # like "assert isinstance(...)"
from beartype.roar import BeartypeDoorHintViolation

from simulation.helper.exceptions import AuctionClosedException, BidMalformedException
from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.world.markets.interfaces.bidder_interface import BidderInterface

BidT = TypeVar("BidT")
ResultT = TypeVar("ResultT")


class Auction(SimulationBase, ABC, Generic[BidT, ResultT]):
    """
    Abstract auction collecting bids and clearing them to a result.

    Subclasses define the bid and result syntax, the auction process,
    and the clearing mechanism.

    Parameters
    ----------
    sim : SimulationContext
        Simulation context.
    """

    __slots__ = (
        "_bid_syntax",
        "_bids",
        "_env",
        "_is_open",
        "_process",
        "_result",
        "_result_syntax",
        "cleared",
        "open_for_bidding",
    )

    def __init__(self, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._env = sim.env
        self._is_open = False
        self._bid_syntax: type[BidT] | type[None] = type(None)
        self._bids: BidT | None = None
        self._result_syntax: type[ResultT] | type[None] = type(None)
        self._result: ResultT | None = None

        self.open_for_bidding = self._env.event()
        self.cleared = self._env.event()

        self._process = self._env.process(self.run())

    @property
    def result(self) -> ResultT | None:
        """Return the clearing result, or None if not yet cleared."""
        return self._result

    @property
    def is_open(self) -> bool:
        """Return whether the auction accepts bids."""
        return self._is_open

    @abstractmethod
    def run(self) -> Generator[Event, None, None]:
        """
        Drive the auction lifecycle.

        Yields
        ------
        Event
            Events awaited between auction rounds.
        """

    @abstractmethod
    def clear(self) -> None:
        """Clear the auction and compute the result."""

    @abstractmethod
    def register_participant(self, participant: BidderInterface[BidT, ResultT]) -> int:
        """
        Register a bidder with the auction.

        Parameters
        ----------
        participant : BidderInterface
            Bidder to register.

        Returns
        -------
        int
            Assigned participant identifier.
        """

    def place_bid(self, bid: BidT) -> None:
        """
        Place a bid after validating syntax and auction state.

        Parameters
        ----------
        bid : BidT
            Bid conforming to the auction's bid syntax.

        Raises
        ------
        BidMalformedException
            If the bid does not conform to the bid syntax.
        AuctionClosedException
            If the auction is not open for bidding.
        """
        # check that bid conforms to the syntax
        try:
            die_if_unbearable(bid, self._bid_syntax)
        except BeartypeDoorHintViolation as e:
            raise BidMalformedException(
                f"{bid} is not of type {self._bid_syntax}"
            ) from e

        # check that auction is still open
        if not self._is_open:
            raise AuctionClosedException()

        self._update_bids(bid)

    @abstractmethod
    def _update_bids(self, single_bid: BidT) -> None:
        """
        Merge a single bid into the auction's bids.

        The auctioneer should implement the specifics per auction type.

        Parameters
        ----------
        single_bid : BidT
            Bid to merge.
        """
