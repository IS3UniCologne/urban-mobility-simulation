"""Interface for auction participants."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic

from simulation.world.markets.auction import Auction, BidT, ResultT

if TYPE_CHECKING:
    from simpy import Environment


class BidderInterface(Generic[BidT, ResultT]):
    """
    Auction participant that places bids and receives results.

    Parameters
    ----------
    env : Environment
        Simpy environment.
    auction : Auction
        Auction to register with.

    Attributes
    ----------
    result_announced : Event
        Succeeds when the auction result is announced.
    bidding_done : Event
        Succeeds when this bidder has placed its bids.
    """

    def __init__(self, env: Environment, auction: Auction[BidT, ResultT]) -> None:
        self._env = env
        self._auction = auction
        self._auction_participant_id = self._auction.register_participant(self)

        self._bids: BidT | None = None
        self._result: ResultT | None = None

        # Events
        self.result_announced = self._env.event()
        self.bidding_done = self._env.event()

    @property
    def auction_participant_id(self) -> int:
        """Return the auction participant identifier."""
        return self._auction_participant_id

    # @abstractmethod
    # def wait_for_bidding(self):
    #     """
    #     The bidder should wait for the auction to open and is expected to then place their bids.
    #     """
