class RLStrategy:
    """Strictly returns the bids from Gym, raising an error if they are missing."""
    def __init__(self, env, auction):
        self._env = env
        self._auction = auction
        self.next_action = env.event()

    def get_bids(self, operator_instance, auctioned_timeslot, auctioned_capacity):
        #yield self._auction.open_for_bidding
        
        action_matrix = yield self.next_action

        self.next_action = self._env.event()
        
        if action_matrix is None:
            raise ValueError(
                f"SimPy t={self._env.now}: RL Agent provided a 'None' action "
                f"for timeslot {auctioned_timeslot}!"
            )
            
        return action_matrix