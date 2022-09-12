import random


class StateTransition:

    def __init__(self, state, action, reward, vehicles_soc_in_destination_hex_buckets, soc_at_destination):
        self._state = state
        self._action = action
        self._reward = reward
        self._vehicles_soc_at_destination_buckets = vehicles_soc_in_destination_hex_buckets
        self._next_state = None
        self._soc_at_destination = soc_at_destination

    def generate_next_state(self,
                            next_closest_vehicles_soc,
                            next_destination_soc_buckets,
                            next_destination_dummies,
                            next_expected_energy_consumption,
                            next_time_bucket_list,
                            next_charging_station_destination_free_capacity,
                            next_number_waiting_vehicles_for_charging,
                            next_charging_station_indication):
        # put our car in soc_buckets list!
        self._vehicles_soc_at_destination_buckets[int(self._soc_at_destination / 0.1001)] += 1

        self._next_state = self._vehicles_soc_at_destination_buckets + \
                           next_destination_soc_buckets + \
                           next_destination_dummies + \
                           next_expected_energy_consumption + \
                           next_time_bucket_list + \
                           next_charging_station_destination_free_capacity + \
                           next_number_waiting_vehicles_for_charging + \
                           next_charging_station_indication

    def get_transition_for_replay(self):
        return self._state, self._action, self._reward, self._next_state
