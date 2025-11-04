from simpy import Environment  # noqa: D100

from simulation.world.markets.auction import Auction
from tracking.tracking_interface import TrackingInterface


class BidderInterface(TrackingInterface):  # noqa: D101
    exposes = ["auction_participant_id", "_bids", "_result"]  # noqa: RUF012

    def __init__(self, env: Environment, auction: Auction) -> None:
        self._env = env
        self._auction = auction
        self._auction_participant_id = self._auction.register_participant(self)

        self._bids = None
        self._result = None

        # Events
        self.result_announced = self._env.event()
        self.bidding_done = self._env.event()

    @property
    def auction_participant_id(self):  # noqa: ANN201, D102
        return self._auction_participant_id

    def dump(self, exposed_only: bool = True) -> dict:  # noqa: D102
        if exposed_only:
            return {x: self.get(x) for x in self.exposes}
        else:
            raise NotImplementedError

    # @abstractmethod
    # def wait_for_bidding(self):
    #     """
    #     The bidder should wait for the auction to open and is expected to then place their bids.
    #     """
