from abc import ABC, abstractmethod  # noqa: D100
from typing import Any

from beartype.door import die_if_unbearable  # like "assert isinstance(...)"
from beartype.roar import BeartypeDoorHintViolation

from simulation.context.simulation_context import SimulationContext
from simulation.helper.simulation_base import SimulationBase


class BidMalformedException(Exception):  # noqa: D101
    pass


class AuctionClosedException(Exception):  # noqa: D101
    pass


class Auction(SimulationBase, ABC):  # noqa: D101
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
        self._bid_syntax: type = Any
        self._bids: self._bid_syntax = None
        self._result_syntax: type = Any
        self._result: self._result_syntax = None

        self.open_for_bidding = self._env.event()
        self.cleared = self._env.event()

        self._process = self._env.process(self.run())

    @property
    def result(self):  # noqa: ANN201, D102
        return self._result

    @property
    def is_open(self):  # noqa: ANN201, D102
        return self._is_open

    @abstractmethod
    def run(self):  # noqa: ANN201, D102
        pass

    @abstractmethod
    def clear(self):  # noqa: ANN201, D102
        pass

    def place_bid(self, bid):  # noqa: ANN001, ANN201, D102
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
    def _update_bids(self, single_bid):  # noqa: ANN001, ANN202
        """
        This method updates the auction's bids. The auctioneer should implement the specifics per auction type."""  # noqa: D200, D401, D404
        pass
