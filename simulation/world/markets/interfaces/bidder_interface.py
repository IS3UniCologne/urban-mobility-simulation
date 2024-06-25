from simpy import Environment

from simulation.world.markets.auction import Auction


class BidderInterface:
    def __init__(self, env: Environment, auction: Auction):
        self._env = env
        self._auction = auction

        # Events
        self.result_announced = self._env.event()

    # @abstractmethod
    # def wait_for_bidding(self):
    #     """
    #     The bidder should wait for the auction to open and is expected to then place their bids.
    #     """
