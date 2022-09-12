import os
import pickle
import numpy as np
import torch as T
import sys

class SavedModelAgent:

    def __init__(self, vehicle_type, number_closest_vehicles):
        """

        :param vehicle_type: car, scooter, kickscooter
        :param number_closest_vehicles:
        """

        model_path = os.path.join('simulation', 'om_agent', 'results', 'models')

        model = [model_name for model_name in os.listdir(model_path) if vehicle_type in model_name][-1]

        self.dqn_policy = pickle.load(open(os.path.join(model_path, model), 'rb'))
        self.number_of_closest_vehicles = number_closest_vehicles
        self.number_of_executed_actions = 0

    def choose_action(self, state, vehicle_objects):

        # if no vehicle is available, return 0, None
        if not vehicle_objects:
            return 0, None

        #get soc of closest vehicles from state
        vehicle_objects_soc = np.array([vehicle.current_relative_state_of_charge for vehicle in vehicle_objects])

        # check for exploration vs. exploitation
        self.number_of_executed_actions += 1

        with T.no_grad():
            # ca(r)st
            state = T.Tensor(state).to(self.dqn_policy.device)
            # t.max(1) will return largest column value of each row.
            # second column on max result is index of where max element was
            # found, so we pick action with the larger expected reward.
            q_values = np.array(self.dqn_policy(state))

            # sort q_values
            q_values_dict = {idx: q_value for idx, q_value in enumerate(q_values)}
            q_values_dict = dict(sorted(q_values_dict.items(), key=lambda item: item[1], reverse=True))

            for bucket_index in q_values_dict.keys():
                # extract soc bucket bounds
                soc_bucket_lower_bound = bucket_index / 10
                soc_bucket_upper_bound = (bucket_index / 10) + 0.1

                # we found that there are some vehicles with SOC > 1.0
                if bucket_index == 9:
                    soc_bucket_upper_bound += 1

                # find vehicle within buckets soc
                for vehicle_idx, vehicle_soc in enumerate(vehicle_objects_soc):
                    if soc_bucket_lower_bound <= vehicle_soc < soc_bucket_upper_bound:
                        return bucket_index, vehicle_objects[vehicle_idx]
            # probably not needed:
            else:
                print("ALLDA hier ist irgendwaf faul")
                sys.exit(-1)

    def learn(self, states, actions, rewards, next_states):
        pass

    def save_models(self, episode):
        pass
