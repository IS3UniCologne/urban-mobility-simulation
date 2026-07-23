class RLStrategy:
    """Strictly returns the bids from Gym, raising an error if they are missing."""
    def __init__(self, env, operator, auction):
        self._env = env
        self._auction = auction
        self.next_action = env.event()
        self._operator = operator

    def get_bids(self, operations, auctioned_timeslot, auctioned_capacity):
        action_matrix = yield self.next_action

        self.next_action = self._env.event()
        
        if action_matrix is None:
            raise ValueError(
                f"SimPy t={self._env.now}: RL Agent provided a 'None' action "
                f"for timeslot {auctioned_timeslot}!"
            )
            
        valid_uids = {v.uid for v in self._operator.fleet.vehicles}

        filtered_bids = {}
        for loc, bids in action_matrix.items():
            if isinstance(bids, list):
                filtered_bids[loc] = [
                    bid for bid in bids 
                    if isinstance(bid, (tuple, list)) and len(bid) >= 4 and bid[3] in valid_uids
                ]
            else:
                filtered_bids[loc] = bids

        return filtered_bids