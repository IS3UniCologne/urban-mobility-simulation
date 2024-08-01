from abc import ABC, abstractmethod
from typing import Any

from beartype.door import die_if_unbearable  # like "assert isinstance(...)"
from beartype.roar import BeartypeDoorHintViolation
from simpy import Environment

from simulation.helper.configuration.configuration import Configuration


class BidMalformedException(Exception):
    pass


class AuctionClosedException(Exception):
    pass


class Auction(ABC):
    __slots__ = (
        "_env",
        "_config",
        "_start_condition",
        "_end_condition",
        "_is_open",
        "_bid_syntax",
        "_bids",
        "_result_syntax",
        "_result",
        "open_for_bidding",
        "cleared",
        "_process",
    )

    def __init__(self, env: Environment, start_condition, end_condition) -> None:
        self._env = env
        self._config = Configuration.instance()
        self._start_condition = start_condition
        self._end_condition = end_condition
        self._is_open = False
        self._bid_syntax: type = Any
        self._bids: self._bid_syntax = None
        self._result_syntax: type = Any
        self._result: self._result_syntax = None

        self.open_for_bidding = self._env.event()
        self.cleared = self._env.event()

        self._process = self._env.process(self.run())

    @property
    def result(self):
        return self._result

    @property
    def is_open(self):
        return self._is_open

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def clear(self):
        pass

    def place_bid(self, bid):
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
    def _update_bids(self, single_bid):
        """
        This method updates the auction's bids. The auctioneer should implement the specifics per auction type."""
        pass
