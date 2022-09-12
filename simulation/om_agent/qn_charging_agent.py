import os
import pickle
import numpy as np
import sys
from simulation.om_agent.dqn import DQN
import pandas as pd
import random
import math
import torch as T
import torch.nn as nn


class DQNChargingAgent:

    def __init__(self, gamma, lr,
                 dqn_policy: DQN,
                 dqn_target: DQN,
                 eps_start,
                 eps_end,
                 eps_decay,
                 target_update,
                 vehicle_type):
        # networks
        self.dqn_policy = dqn_policy
        self.dqn_target = dqn_target
        # params
        self.eps_start = eps_start
        self.eps_end = eps_end
        self.eps_decay = eps_decay
        self._gamma = gamma
        self._lr = lr
        self._iteration = 0
        self.target_update = target_update
        self.vehicle_type = vehicle_type
        # tracking
        self.number_of_executed_actions = 0
        self.results_df = pd.DataFrame()
        self.results_path = os.path.join(os.getcwd(), 'simulation', 'om_agent', 'results', f'0_results_{vehicle_type}.csv')
        self.models_path = os.path.join(os.getcwd(), 'simulation', 'om_agent', 'results', 'models')

        self.number_of_closest_vehicles = dqn_policy.output_dims
        self.eps_threshold = eps_start

    def choose_action(self, state, vehicle_objects):
        """
        Return action based on state
        :param state: State
        :type state: list
        :return: action
        :rtype: list
        """

        # if no vehicle is available, return 0, None
        if not vehicle_objects:
            return 0, None

        #get soc of closest vehicles from state
        vehicle_objects_soc = np.array([vehicle.current_relative_state_of_charge for vehicle in vehicle_objects])


        # check for exploration vs. exploitation
        sample = random.random()
        self.eps_threshold = self.eps_end + (self.eps_start - self.eps_end) * \
                        math.exp(-1. * self.number_of_executed_actions / self.eps_decay)
        self.number_of_executed_actions += 1

        if sample > self.eps_threshold:
            #exploitation
            with T.no_grad():
                # ca(r)st
                state = T.Tensor(state).to(self.dqn_policy.device)
                # t.max(1) will return largest column value of each row.
                # second column on max result is index of where max element was
                # found, so we pick action with the larger expected reward.
                q_values = np.array(self.dqn_policy(state))

                #sort q_values
                q_values_dict = {idx: q_value for idx, q_value in enumerate(q_values)}
                q_values_dict = dict(sorted(q_values_dict.items(), key=lambda item: item[1], reverse=True))

                for bucket_index in q_values_dict.keys():
                    # extract soc bucket bounds
                    soc_bucket_lower_bound = bucket_index / 10
                    soc_bucket_upper_bound = (bucket_index/ 10) + 0.1

                    # we found that there are some vehicles with SOC > 1.0
                    if bucket_index == 9:
                        soc_bucket_upper_bound += 1

                    #find vehicle within buckets soc
                    for vehicle_idx, vehicle_soc in enumerate(vehicle_objects_soc):
                        if soc_bucket_lower_bound <= vehicle_soc < soc_bucket_upper_bound:
                            return bucket_index, vehicle_objects[vehicle_idx]
                # probably not needed:
                else:
                    print("ALLDA hier ist irgendwaf faul")
                    sys.exit(-1)

        else:
            #exploration
            action = random.randrange(self.dqn_policy.output_dims)
            while state[action] < 1:
                action = random.randrange(self.dqn_policy.output_dims)

            # extract soc bucket bounds
            soc_bucket_lower_bound = action / 10
            soc_bucket_upper_bound = (action / 10) + 0.1
            if action == 9:
                soc_bucket_upper_bound += 1

            for vehicle_idx, vehicle_soc in enumerate(vehicle_objects_soc):
                if soc_bucket_lower_bound <= vehicle_soc < soc_bucket_upper_bound:
                    return action, vehicle_objects[vehicle_idx]
            # probably not needed:
            else:
                print("ALLDA hier ist irgendwaf faul")
                sys.exit(-1)

    def learn(self, states, actions, rewards, next_states):

        # transform to tensors
        states_tensor = T.tensor(states, dtype=T.float).to(self.dqn_policy.device)
        actions_tensor = T.tensor(actions, dtype=T.int64).to(self.dqn_policy.device)
        rewards_tensor = T.tensor(rewards, dtype=T.float).to(self.dqn_policy.device)
        next_states_tensor = T.tensor(next_states, dtype=T.float).to(self.dqn_policy.device)

        ##################### 1: Update policy network ############################

        # Compute Q(s_t, a) - the model computes Q(s_t), then we select the
        # columns of actions taken. These are the actions which would've been taken
        # for each batch state according to policy_net

        state_action_values = self.dqn_policy.forward(states_tensor).gather(1, actions_tensor)

        # Compute V(s_{t + 1}) for all next states.
        # ATTENTION: We only use q-values for actions which are actually possible!!
        next_states_q_values = self.dqn_target.forward(next_states_tensor)#.max(-1)[0].detach()

        next_state_highest_q_value_list = np.array([])

        for idx, q_values in enumerate(next_states_q_values):

            q_values_dict = {idx: q_value.item() for idx, q_value in enumerate(q_values)}
            q_values_dict = dict(sorted(q_values_dict.items(), key=lambda item: item[1], reverse=True))
            vehicles_in_soc_buckets = next_states_tensor[idx][:10]
            for idx in q_values_dict.keys():
                if vehicles_in_soc_buckets[idx] > 0:
                    next_state_highest_q_value_list = np.append(next_state_highest_q_value_list, q_values_dict[idx])
                    break
            else:
                print("ALLA HIER IF WAF FAUL BRO. qn_charging_agent.py method learn")
                sys.exit(0)

        next_state_highest_q_value_tensor = T.from_numpy(next_state_highest_q_value_list)

        target_state_action_values = (next_state_highest_q_value_tensor * self._gamma) + rewards_tensor

        # Compute Huber loss
        criterion = nn.SmoothL1Loss()
        loss = criterion(state_action_values, target_state_action_values.unsqueeze(1))

        # Optimize the model
        self.dqn_policy.optimizer.zero_grad()
        loss.backward()
        self.dqn_policy.optimizer.step()

        # update target network
        if self.number_of_executed_actions % self.target_update == 0:
            self.dqn_target.load_state_dict(self.dqn_policy.state_dict())

        ##################### Track metrics ###############################

        # track every 100 actions
        if self.number_of_executed_actions % 100 == 0:

            # print(f"Action {self.number_of_executed_actions} executed!")

            q_values_for_fixed_state = self.get_q_values_for_fixed_state_with_charging_station()
            q_values_for_fixed_state_without_charging_station = self.get_q_values_for_fixed_state_without_charging_station()

            result = {
                'policy_loss': [loss.item()],
                'reward [0]': [rewards[0].item()],
                'epsilon': [self.eps_threshold],
                'executed_actions': [self.number_of_executed_actions],
            }

            # append q values for fixed state into results dictionary
            for idx, q_value in enumerate(q_values_for_fixed_state):
                result[f'q_value_for_fixed_action_with_charging{idx}'] = q_value

            for idx, q_value in enumerate(q_values_for_fixed_state_without_charging_station):
                result[f'q_value_for_fixed_action_without_charging{idx}'] = q_value


            self.results_df = pd.concat([self.results_df, pd.DataFrame(result)], axis=0)
            self.results_df.to_csv(self.results_path)

    def save_models(self, episode):
        # policy net
        pickle.dump(self.dqn_policy, open(os.path.join(self.models_path, f'policy_net_{self.vehicle_type}_{episode}.sav'), 'wb'))

    def get_q_values_for_fixed_state_with_charging_station(self):

        socs = [1,1,1,1,1,1,1,1,1,1]

        # state where destination includes charging station, expected energy consumption is valid for all 3 vehicles
        state = socs + [0, 0, 2, 1, 4, 2, 3, 3, 0, 1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.050952115725809544, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 0, 1]

        with T.no_grad():
            # ca(r)st
            state = T.Tensor(state).to(self.dqn_policy.device)
            q_values = np.array(self.dqn_policy(state))

        return q_values


    def get_q_values_for_fixed_state_without_charging_station(self):

        socs = [1,1,1,1,1,1,1,1,1,1]

        # state where destination includes charging station, expected energy consumption is valid for all 3 vehicles
        state = socs + [0, 0, 2, 1, 4, 2, 3, 3, 0, 1, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.050952115725809544, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

        with T.no_grad():
            # ca(r)st
            state = T.Tensor(state).to(self.dqn_policy.device)
            q_values = np.array(self.dqn_policy(state))

        return q_values