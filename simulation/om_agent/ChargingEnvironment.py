from sklearn.preprocessing import MinMaxScaler

from simulation.helper.configuration.configuration import Configuration
import numpy as np
from copy import deepcopy
import sys
import logging

from simulation.om_agent.kpi_tracker import KPITracker
from simulation.vehicle.vehicle import VehicleState
from .StateTransition import StateTransition
from ..infrastructure.route import Route

from ..vehicle.shared_car import SharedCar
from ..vehicle.shared_kick_scooter import SharedKickScooter
from ..vehicle.shared_scooter import SharedScooter
from simulation.helper.time import SimulationTime
from simulation.helper.time import SimulationTimeConverter
from simulation.om_agent.ChargingStationHandler import ChargingStationHandler
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.environment.geodesic_position import GeodesicPosition


class ChargingEnvironment:

    def __init__(self, rl_agent_car, rl_agent_scooter, rl_agent_kickscooter, replay_memory_car,
                 replay_memory_scooter, replay_memory_kickscooter, soc_bucket_boundaries, kpi_tracker: KPITracker,
                 reward_type: str, env):

        self.rl_agent_car = rl_agent_car
        self.rl_agent_scooter = rl_agent_scooter
        self.rl_agent_kickscooter = rl_agent_kickscooter
        self._mixed_fleet = None

        self.replay_memory_car = replay_memory_car
        self.replay_memory_scooter = replay_memory_scooter
        self.replay_memory_kickscooter = replay_memory_kickscooter

        # helper
        self.hex_id_list = Configuration.instance().get_hex_id_list()
        self.number_of_hexagons = len(self.hex_id_list)
        self.hexagon_dummies = np.zeros(self.number_of_hexagons)

        self.car_transitions = {hex_id: [] for hex_id in self.hex_id_list}
        self.scooter_transitions = {hex_id: [] for hex_id in self.hex_id_list}
        self.kickscooter_transitions = {hex_id: [] for hex_id in self.hex_id_list}

        # state helper
        # {hex_id : [#bucket_1, #bucket_2, #bucket_3], ...}
        self.state_bucket_dummy = [0] * (len(soc_bucket_boundaries) - 1)

        self.number_of_closest_vehicles = rl_agent_car.dqn_policy.output_dims

        self.charging_stations = Configuration.instance().shared_vehicle_operator_config.base_regions

        # threshold when vehicles are "able" to start charging
        self.recharge_threshold = Configuration.instance().shared_vehicle_operator_config.recharge_threshold  # e.g. 0.1

        # threshold when vehicles "risk" to get stuck /not used anymore...
        self.critical_soc_threshold = Configuration.instance().shared_vehicle_operator_config.critical_soc_threshold

        self.soc_bucket_boundaries = soc_bucket_boundaries

        self.kpi_tracker = kpi_tracker

        self._number_cars_actions = 0

        self.reward_type = reward_type

        self._geodesic_environment = GeodesicEnvironment.getInstance()

        self._temporal_resolution = Configuration.instance().temporal_resolution.value
        self._dummy_list = [0] * (int(24 / self._temporal_resolution))

        self._env = env

        self._car_scaler = MinMaxScaler().fit(
            np.array([0, Configuration.instance().get_vehicle_config("SharedCar").number_vehicles]).reshape(-1, 1))
        self._scooter_scaler = MinMaxScaler().fit(
            np.array([0, Configuration.instance().get_vehicle_config("SharedScooter").number_vehicles]).reshape(-1, 1))
        self._kickscooter_scaler = MinMaxScaler().fit(
            np.array([0, Configuration.instance().get_vehicle_config("SharedKickScooter").number_vehicles]).reshape(-1,
                                                                                                                    1))

        self._charging_station_handler = None

        # track waiting vehicle for charging
        self.waiting_cars = 0
        self.waiting_scooters = 0
        self.waiting_kickscooters = 0

    def reset_transitions(self):
        self.car_transitions = {hex_id: [] for hex_id in self.hex_id_list}
        self.scooter_transitions = {hex_id: [] for hex_id in self.hex_id_list}
        self.kickscooter_transitions = {hex_id: [] for hex_id in self.hex_id_list}

    @property
    def charging_station_handler(self):
        return self._charging_station_handler

    @charging_station_handler.setter
    def charging_station_handler(self, charging_station_handler):
        self._charging_station_handler = charging_station_handler

    @property
    def mixed_fleet(self):
        return self._mixed_fleet

    @mixed_fleet.setter
    def mixed_fleet(self, mixed_fleet):
        self._mixed_fleet = mixed_fleet

    @property
    def env(self):
        return self._env

    @env.setter
    def env(self, env):
        self._env = env
        self._time = SimulationTime(env)

    def single_run_cars(self, user):

        # obtain state
        state, closest_vehicles, vehicles_soc_in_destination_hex, \
        next_closest_vehicles_soc, next_destination_soc_buckets, next_destination_dummies, \
        next_expected_energy_consumption, next_time_bucket_list, next_charging_station_destination_free_capacity, \
        next_number_waiting_vehicles_for_charging, next_charging_station_indication \
            = self.get_state_and_closest_vehicles('SharedCar', user)

        # select action and map to vehicle
        action, selected_vehicle = self.rl_agent_car.choose_action(state, closest_vehicles)

        if selected_vehicle is None:
            return None

        # track origin destination average SOC
        self.kpi_tracker.execute_soc_origin_destination_tracking(user, selected_vehicle, 'SharedCar')

        # obtain reward
        reward = self.get_reward(selected_vehicle, user)
        self.kpi_tracker.increase_car_agent_reward_sum(reward)

        transition = StateTransition(state, action, reward, vehicles_soc_in_destination_hex,
                                     self.get_soc_at_destination(selected_vehicle, user))

        # append current transition for "waiting"
        self.car_transitions[user.transport_task.destination.get_default_hexagon()].append(transition)

        # complete all "waiting" transitions and store in replay memory
        for transition in self.car_transitions[user.transport_task.origin.get_default_hexagon()]:

            next_time_bucket_list = deepcopy(self._dummy_list)
            next_time_bucket_list[self.time_bucket] = 1

            transition.generate_next_state(next_closest_vehicles_soc,
                                           next_destination_soc_buckets,
                                           next_destination_dummies,
                                           next_expected_energy_consumption,
                                           next_time_bucket_list,
                                           next_charging_station_destination_free_capacity,
                                           next_number_waiting_vehicles_for_charging,
                                           next_charging_station_indication)

            state, action, reward, next_state = transition.get_transition_for_replay()
            self.replay_memory_car.store_transition(state, action, reward, next_state)

        # 'remove' all completed transitions
        self.car_transitions[user.transport_task.origin.get_default_hexagon()] = []

        # only learn if enough samples are present

        if self.replay_memory_car.get_mem_cntr() > self.replay_memory_car.batch_size \
                and self.kpi_tracker.charging_agent_active_episodes >= 1:
            # sample batch_size number of states, actions, rewards, next_states
            states, actions, rewards, next_states = self.replay_memory_car.sample_memory(
                self.replay_memory_car.batch_size)
            self.rl_agent_car.learn(states, actions, rewards, next_states)

        self._number_cars_actions += 1
        if self._number_cars_actions % 2000 == 0:
            logging.error(f"User trip from {user.transport_task.origin} to {user.transport_task.destination}."
                          f"Destination includes charging station: {user.transport_task.destination in self.charging_stations} "
                          f"Closest vehicles soc: {[vehicle.current_relative_state_of_charge if vehicle != None else '' for vehicle in closest_vehicles]}"
                          f"Selected vehicle:{None if selected_vehicle == None else selected_vehicle.current_relative_state_of_charge}")

        return selected_vehicle

    def single_run_scooters(self, user):
        # obtain state
        state, closest_vehicles, vehicles_soc_in_destination_hex, \
        next_closest_vehicles_soc, next_destination_soc_buckets, next_destination_dummies, \
        next_expected_energy_consumption, next_time_bucket_list, next_charging_station_destination_free_capacity, \
        next_number_waiting_vehicles_for_charging, next_charging_station_indication \
            = self.get_state_and_closest_vehicles('SharedScooter', user)

        # select action and map to vehicle
        action, selected_vehicle = self.rl_agent_scooter.choose_action(state, closest_vehicles)

        if selected_vehicle is None:
            return None

        # track origin destination average SOC
        self.kpi_tracker.execute_soc_origin_destination_tracking(user, selected_vehicle, 'SharedScooter')

        # obtain reward
        reward = self.get_reward(selected_vehicle, user)
        self.kpi_tracker.increase_scooter_agent_reward_sum(reward)

        transition = StateTransition(state, action, reward, vehicles_soc_in_destination_hex,
                                     self.get_soc_at_destination(selected_vehicle, user))

        # append current transition for "waiting"
        self.scooter_transitions[user.transport_task.destination.get_default_hexagon()].append(transition)

        # complete all "waiting" transitions and store in replay memory
        for transition in self.scooter_transitions[user.transport_task.origin.get_default_hexagon()]:

            next_time_bucket_list = deepcopy(self._dummy_list)
            next_time_bucket_list[self.time_bucket] = 1

            transition.generate_next_state(next_closest_vehicles_soc,
                                           next_destination_soc_buckets,
                                           next_destination_dummies,
                                           next_expected_energy_consumption,
                                           next_time_bucket_list,
                                           next_charging_station_destination_free_capacity,
                                           next_number_waiting_vehicles_for_charging,
                                           next_charging_station_indication)

            state, action, reward, next_state = transition.get_transition_for_replay()
            self.replay_memory_scooter.store_transition(state, action, reward, next_state)

        # 'remove' all completed transitions
        self.scooter_transitions[user.transport_task.origin.get_default_hexagon()] = []

        # only learn if enough samples are present
        if self.replay_memory_scooter.get_mem_cntr() > self.replay_memory_scooter.batch_size \
                and self.kpi_tracker.charging_agent_active_episodes >= 1:
            # sample batch_size number of states, actions, rewards, next_states
            states, actions, rewards, next_states = self.replay_memory_scooter.sample_memory(
                self.replay_memory_scooter.batch_size)
            self.rl_agent_scooter.learn(states, actions, rewards, next_states)
        return selected_vehicle

    def single_run_kickscooters(self, user):

        # obtain state
        state, closest_vehicles, vehicles_soc_in_destination_hex, \
        next_closest_vehicles_soc, next_destination_soc_buckets, next_destination_dummies, \
        next_expected_energy_consumption, next_time_bucket_list, next_charging_station_destination_free_capacity, \
        next_number_waiting_vehicles_for_charging, next_charging_station_indication \
            = self.get_state_and_closest_vehicles('SharedKickscooter', user)

        # select action and map to vehicle
        action, selected_vehicle = self.rl_agent_kickscooter.choose_action(state, closest_vehicles)

        if selected_vehicle is None:
            return None

        # track origin destination average SOC
        self.kpi_tracker.execute_soc_origin_destination_tracking(user, selected_vehicle, 'SharedKickscooter')

        # obtain reward
        reward = self.get_reward(selected_vehicle, user)
        self.kpi_tracker.increase_kickscooter_agent_reward_sum(reward)

        transition = StateTransition(state, action, reward, vehicles_soc_in_destination_hex,
                                     self.get_soc_at_destination(selected_vehicle, user))

        # append current transition for "waiting"
        self.kickscooter_transitions[user.transport_task.destination.get_default_hexagon()].append(transition)

        # complete all "waiting" transitions and store in replay memory
        for transition in self.kickscooter_transitions[user.transport_task.origin.get_default_hexagon()]:

            next_time_bucket_list = deepcopy(self._dummy_list)
            next_time_bucket_list[self.time_bucket] = 1

            transition.generate_next_state(next_closest_vehicles_soc,
                                           next_destination_soc_buckets,
                                           next_destination_dummies,
                                           next_expected_energy_consumption,
                                           next_time_bucket_list,
                                           next_charging_station_destination_free_capacity,
                                           next_number_waiting_vehicles_for_charging,
                                           next_charging_station_indication)

            state, action, reward, next_state = transition.get_transition_for_replay()
            self.replay_memory_kickscooter.store_transition(state, action, reward, next_state)

        # 'remove' all completed transitions
        self.kickscooter_transitions[user.transport_task.origin.get_default_hexagon()] = []

        # only learn if enough samples are present
        if self.replay_memory_kickscooter.get_mem_cntr() > self.replay_memory_kickscooter.batch_size \
                and self.kpi_tracker.charging_agent_active_episodes >= 1:
            # sample batch_size number of states, actions, rewards, next_states
            states, actions, rewards, next_states = self.replay_memory_kickscooter.sample_memory(
                self.replay_memory_kickscooter.batch_size)
            self.rl_agent_kickscooter.learn(states, actions, rewards, next_states)

        return selected_vehicle

    def get_soc_at_destination(self, selected_vehicle, user):

        distance = user.transport_task.origin >> user.transport_task.destination
        energy_consumed_absolute = selected_vehicle.energy_consumption * distance / 1000
        energy_consumed_relative = energy_consumed_absolute / selected_vehicle.max_state_of_charge
        soc_at_destination = selected_vehicle.current_relative_state_of_charge - energy_consumed_relative

        if soc_at_destination < self.recharge_threshold and user.transport_task.destination.get_default_hexagon() in self.charging_stations:
            return 1

        else:
            return soc_at_destination

    def get_reward(self, selected_vehicle, user):
        """
        Reward = soc which will be charged after used arrives at destination
        """

        ##########################charging amount reward###############################################################
        if self.reward_type == 'charging_amount':
            return self.get_charging_amount(selected_vehicle=selected_vehicle, user=user)

        elif self.reward_type == 'critical_soc_penalty':
            # if agent produces vehicle below critical soc, penalize with -1.
            # if agent charges critical SOC vehicle, reward with 0.5
            # Otherwise, reward = 0
            distance = user.transport_task.origin >> user.transport_task.destination
            energy_consumed_absolute = selected_vehicle.energy_consumption * distance / 1000
            energy_consumed_relative = energy_consumed_absolute / selected_vehicle.max_state_of_charge
            if (selected_vehicle.current_relative_state_of_charge - energy_consumed_relative) < \
                    self.critical_soc_threshold:
                return -1
            elif selected_vehicle.current_relative_state_of_charge < self.critical_soc_threshold and \
                user.transport_task.destination.get_default_hexagon() in self.charging_stations:
                return 0.5
            else:
                return 0

        ########################## vehicles below threshold reward ####################################################
        elif self.reward_type == 'vehicles_below_critical_threshold':

            vehicles_below_critical_threshold = self.get_number_of_vehicles_below_critical_threshold(selected_vehicle,
                                                                                                     user)
            return (-1 * vehicles_below_critical_threshold)

        ######################################### sum_soc ##############################################################

        elif self.reward_type == 'sum_soc':
            vehicle_list = self.get_vehicle_list(selected_vehicle)
            sum_soc_relative = 0
            for vehicle in vehicle_list:
                sum_soc_relative += vehicle.current_relative_state_of_charge

            # normalize sum_soc_relative
            scaler = self.get_vehicle_type_scaler(selected_vehicle)
            normalized_sum_soc_relative = scaler.transform(np.array(sum_soc_relative).reshape(1, -1))

            return normalized_sum_soc_relative[0][0]


        ######################################### charging_amount_threshold_penalty ####################################
        # Use charging amount per action and penalize with number of vehicles below critical threshold

        elif self.reward_type == 'charging_amount_threshold_penalty':
            charging_amount = self.get_charging_amount(selected_vehicle=selected_vehicle, user=user)
            vehicles_below_critical_threshold = self.get_number_of_vehicles_below_critical_threshold(selected_vehicle,
                                                                                                     user)
            # normalize vehicles_below_critical_threshold
            scaler = self.get_vehicle_type_scaler(selected_vehicle)
            normalized_vehicles_below_critical_threshold = scaler.transform(
                np.array(vehicles_below_critical_threshold).reshape(1, -1))

            return (charging_amount - normalized_vehicles_below_critical_threshold[0][0])

        elif self.reward_type == 'delta_threshold_penalty_charging_amount':
            # if charged and no vehicle is waiting for charging at destination:
            # charging amount
            # if charged and more than 0 vehicles are waiting for charging at destination:
            # 1/number_of_waiting_vehicles * charging_amount
            # if not charged:
            # if soc above critical threshold after trip:
            # 0
            # if soc below critical threshold after trip:
            # -1 * (x)

            if isinstance(selected_vehicle, SharedCar):
                waiting_vehicles_for_charging = self.waiting_cars
            elif isinstance(selected_vehicle, SharedScooter):
                waiting_vehicles_for_charging = self.waiting_scooters
            elif isinstance(selected_vehicle, SharedKickScooter):
                waiting_vehicles_for_charging = self.waiting_kickscooters
            else:
                logging.error("Vehicle Type not found")
                sys.exit(-1)

            charging_amount = self.get_charging_amount(selected_vehicle=selected_vehicle, user=user)

            if charging_amount > 0 and waiting_vehicles_for_charging == 0:
                return charging_amount

            elif charging_amount > 0 and waiting_vehicles_for_charging > 0:
                return (1 / waiting_vehicles_for_charging) * charging_amount

            else:
                distance = user.transport_task.origin >> user.transport_task.destination
                energy_consumed_absolute = selected_vehicle.energy_consumption * distance / 1000
                energy_consumed_relative = energy_consumed_absolute / selected_vehicle.max_state_of_charge
                if (selected_vehicle.current_relative_state_of_charge - energy_consumed_relative) > \
                        self.critical_soc_threshold:
                    return 0
                else:
                    return -4

        elif self.reward_type == 'delta_threshold_penalty_charging_amount_amplifier':
            # if charged and no vehicle is waiting for charging at destination:
            # charging amount
            # if charged and more than 0 vehicles are waiting for charging at destination:
            # 1/number_of_waiting_vehicles * charging_amount
            # if not charged:
            # if soc above critical threshold after trip:
            # 0
            # if soc below critical threshold after trip:
            # -1 * (x)

            if isinstance(selected_vehicle, SharedCar):
                waiting_vehicles_for_charging = self.waiting_cars
            elif isinstance(selected_vehicle, SharedScooter):
                waiting_vehicles_for_charging = self.waiting_scooters
            elif isinstance(selected_vehicle, SharedKickScooter):
                waiting_vehicles_for_charging = self.waiting_kickscooters
            else:
                logging.error("Vehicle Type not found")
                sys.exit(-1)

            charging_amount = self.get_charging_amount(selected_vehicle=selected_vehicle, user=user)
            amplifier = 3 if selected_vehicle.current_relative_state_of_charge < self.critical_soc_threshold else 1

            if charging_amount > 0 and waiting_vehicles_for_charging == 0:
                return charging_amount * amplifier

            elif charging_amount > 0 and waiting_vehicles_for_charging > 0:
                return (1 / waiting_vehicles_for_charging) * charging_amount * amplifier

            else:
                distance = user.transport_task.origin >> user.transport_task.destination
                energy_consumed_absolute = selected_vehicle.energy_consumption * distance / 1000
                energy_consumed_relative = energy_consumed_absolute / selected_vehicle.max_state_of_charge
                if (selected_vehicle.current_relative_state_of_charge - energy_consumed_relative) > \
                        self.critical_soc_threshold:
                    return 0
                else:
                    return -4

        elif self.reward_type == 'vehicle_below_or_above_critical_soc':

            distance = user.transport_task.origin >> user.transport_task.destination
            energy_consumed_absolute = selected_vehicle.energy_consumption * distance / 1000
            energy_consumed_relative = energy_consumed_absolute / selected_vehicle.max_state_of_charge

            if (selected_vehicle.current_relative_state_of_charge - energy_consumed_relative) > \
                    self.critical_soc_threshold:
                return 1

            elif user.transport_task.destination.get_default_hexagon() in self.charging_stations:
                if selected_vehicle.current_relative_state_of_charge < self.critical_soc_threshold:
                    return 2
                else:
                    return 1

            else:
                return -5

    def get_charging_amount(self, selected_vehicle, user):
        """
        Charging amount = soc which will be charged after used arrives at destination
        """
        if selected_vehicle == None:
            charging_amount = 0
        elif (user.transport_task.destination.get_default_hexagon() in self.charging_stations):
            current_soc = selected_vehicle.current_state_of_charge
            distance = user.transport_task.origin >> user.transport_task.destination
            energy_consumed = selected_vehicle.energy_consumption * distance / 1000
            charging_amount = 1 - ((current_soc - energy_consumed) / selected_vehicle.max_state_of_charge)

            # set charging_amount to zero if we wont have less soc than the threshold
            if not charging_amount > ((1 - self.recharge_threshold) + 0.01):
                charging_amount = 0
        else:
            charging_amount = 0

        return charging_amount

    def get_state_and_closest_vehicles(self, vehicle_type, user):
        """
        State consists of:
        - origin destination
        - soc for each hexagon
        - n closest vehicles soc
        """

        vehicles_in_origin_hex = []
        vehicles_in_destination_hex = []

        ############################### Origin destination ####################################

        origin_hex_id = user.transport_task.origin.get_default_hexagon()
        destination_hex_id = user.transport_task.destination.get_default_hexagon()

        destination_idx = self.hex_id_list.index(destination_hex_id)
        destination_dummies = deepcopy(self.hexagon_dummies)
        destination_dummies[destination_idx] = 1

        ############################### SOC for each hexagon and Free Capacities ####################################

        # extract vehicle list
        if vehicle_type == 'SharedCar':
            vehicle_list = self.mixed_fleet.cars
            charging_station_destination_free_capacity = self.charging_station_handler.get_car_charging_station_free_capacity(
                destination_hex_id)
        elif vehicle_type == 'SharedScooter':
            vehicle_list = self.mixed_fleet.scooters
            charging_station_destination_free_capacity = self.charging_station_handler.get_scooter_charging_station_free_capacity(
                destination_hex_id)
        elif vehicle_type == 'SharedKickscooter':
            vehicle_list = self.mixed_fleet.kickscooters
            charging_station_destination_free_capacity = self.charging_station_handler.get_kickscooter_charging_station_free_capacity(
                destination_hex_id)
        else:
            raise ValueError

        destination_soc_buckets = deepcopy(self.state_bucket_dummy)
        # count vehicles SOC for destination
        for vehicle in vehicle_list:
            if vehicle.state == VehicleState.PARKING:
                # calculate which soc bucket the vehicle belongs to
                bucket = 100
                for i in range(len(self.soc_bucket_boundaries) - 1):
                    if self.soc_bucket_boundaries[i] <= vehicle.current_relative_state_of_charge < \
                            self.soc_bucket_boundaries[i + 1]:
                        bucket = i
                        break

                if bucket == 100:
                    logging.error(f"SOC Bucket not found.")
                    sys.exit(-1)

                # update dictionary
                vehicle_hex_id = vehicle.position.get_default_hexagon()

                # if vehicle in origin, append to vehicle list
                if vehicle_hex_id == origin_hex_id:
                    vehicles_in_origin_hex.append(vehicle)

                elif vehicle_hex_id == destination_hex_id:
                    destination_soc_buckets[bucket] += 1
                    vehicles_in_destination_hex.append(vehicle)

        ############################## Number of waiting vehicles for charging #############################

        number_waiting_vehicles_for_charging = len([vehicle for vehicle in vehicles_in_destination_hex if
                                                    vehicle.current_relative_state_of_charge < self.recharge_threshold])

        if vehicle_type == 'SharedCar':
            self.waiting_cars = number_waiting_vehicles_for_charging
        elif vehicle_type == 'SharedScooter':
            self.waiting_scooters = number_waiting_vehicles_for_charging
        elif vehicle_type == 'SharedKickscooter':
            self.waiting_kickscooters = number_waiting_vehicles_for_charging
        else:
            logging.error("Vehicle Type not found")
            sys.exit(-1)

        ############################### Closest cars SOC for origin ####################################

        vehicle_distances_dict = {}
        # calculate distance between user and vehicle
        for vehicle in vehicles_in_origin_hex:
            distance_to_vehicle = vehicle.position >> user.position
            if distance_to_vehicle < vehicle.max_walking_distance:
                vehicle_distances_dict[vehicle] = distance_to_vehicle

        closest_vehicles_objects = []
        closest_vehicles_soc_buckets = [0] * 10

        for vehicle in vehicle_distances_dict.keys():
            if vehicle.has_enough_state_of_charge(Route(user.transport_task.origin, user.transport_task.destination).distance):
                closest_vehicles_objects.append(vehicle)
                if vehicle.current_relative_state_of_charge >= 1.0:
                    closest_vehicles_soc_buckets[9] +=1
                else:
                    closest_vehicles_soc_buckets[int(vehicle.current_relative_state_of_charge /0.1)] += 1


        ########################### Charging station #########################
        if destination_hex_id in self.charging_stations:
            charging_station_indication = 1

        else:
            charging_station_indication = 0

        distance = Route(user.transport_task.origin, user.transport_task.destination).distance
        expected_energy_consumption = vehicle_list[0].energy_consumption * distance / 1000 / vehicle_list[
            0].max_state_of_charge

        time_bucket_list = deepcopy(self._dummy_list)
        time_bucket_list[self.time_bucket] = 1

        state = closest_vehicles_soc_buckets + destination_soc_buckets + destination_dummies.tolist() + \
                [expected_energy_consumption] + time_bucket_list + [charging_station_destination_free_capacity] + \
                [number_waiting_vehicles_for_charging] + [charging_station_indication]

        return state, closest_vehicles_objects, destination_soc_buckets, \
               closest_vehicles_soc_buckets, destination_soc_buckets, destination_dummies.tolist(), \
               [expected_energy_consumption], time_bucket_list, [charging_station_destination_free_capacity], \
               [number_waiting_vehicles_for_charging], [charging_station_indication]

    def get_soc_based_matching_vehicle(self, user, vehicle_object):

        origin_hex_id = user.transport_task.origin.get_default_hexagon()

        if isinstance(vehicle_object, SharedCar):
            vehicle_list = self.mixed_fleet.cars

        elif isinstance(vehicle_object, SharedScooter):
            vehicle_list = self.mixed_fleet.scooters

        elif isinstance(vehicle_object, SharedKickScooter):
            vehicle_list = self.mixed_fleet.kickscooters
        else:
            vehicle_list = []

        # get all vehicles in users origin hexagon
        vehicles_in_user_hex = []
        for vehicle in vehicle_list:
            if vehicle.state == VehicleState.PARKING:
                vehicle_hex_id = vehicle.position.get_default_hexagon()
                # if vehicle in origin, append to vehicle list
                if vehicle_hex_id == origin_hex_id:
                    vehicles_in_user_hex.append(vehicle)

        vehicle_distances_dict = {}
        # calculate distance between user and vehicle
        for vehicle in vehicles_in_user_hex:
            distance_to_vehicle = vehicle.position >> user.position
            if distance_to_vehicle < vehicle.max_walking_distance:
                vehicle_distances_dict[vehicle] = distance_to_vehicle

        # sort distances dict by values
        vehicle_distances_dict = dict(sorted(vehicle_distances_dict.items(), key=lambda item: item[1]))

        closest_vehicles_soc = {}

        counter = 0
        for vehicle in vehicle_distances_dict.keys():
            if counter == (self.number_of_closest_vehicles - 1):
                break
            if vehicle.has_enough_state_of_charge(user.transport_task.origin >> user.transport_task.destination):
                closest_vehicles_soc[vehicle] = vehicle.current_relative_state_of_charge
                counter += 1

        # sort for soc
        closest_vehicles_soc = dict(sorted(closest_vehicles_soc.items(), key=lambda item: item[1]))

        if user.transport_task.destination in self.charging_stations:
            return list(closest_vehicles_soc.keys())[0]
        else:
            return list(closest_vehicles_soc.keys())[-1]

    def get_vehicle_list(self, selected_vehicle):

        if isinstance(selected_vehicle, SharedCar):
            vehicle_list = self.mixed_fleet.cars
        elif isinstance(selected_vehicle, SharedScooter):
            vehicle_list = self.mixed_fleet.scooters
        elif isinstance(selected_vehicle, SharedKickScooter):
            vehicle_list = self.mixed_fleet.kickscooters
        else:
            vehicle_list = []
        return vehicle_list

    def get_vehicle_type_scaler(self, selected_vehicle):

        if isinstance(selected_vehicle, SharedCar):
            return self._car_scaler
        elif isinstance(selected_vehicle, SharedScooter):
            return self._scooter_scaler
        elif isinstance(selected_vehicle, SharedKickScooter):
            return self._kickscooter_scaler
        else:
            return None

    def get_number_of_vehicles_below_critical_threshold(self, selected_vehicle, user):
        vehicle_list = self.get_vehicle_list(selected_vehicle)
        vehicles_below_threshold = 0

        for vehicle in vehicle_list:
            if vehicle.current_relative_state_of_charge < self.critical_soc_threshold:
                vehicles_below_threshold += 1

        # calculate expected energy consumption
        if selected_vehicle is not None:
            distance = user.transport_task.origin >> user.transport_task.destination
            expected_energy_consumption = (
                                                  selected_vehicle.energy_consumption * distance / 1000) / selected_vehicle.max_state_of_charge

            # adjust reward, if current action results in charging process
            if selected_vehicle.current_relative_state_of_charge - expected_energy_consumption < self.recharge_threshold:
                if user.transport_task.destination.get_default_hexagon() in self.charging_stations:
                    vehicles_below_threshold -= 1

        return vehicles_below_threshold

    @property
    def time_bucket(self):
        """
        Calculate the current time bucket where the simulation is.
        :return: Number of the time bucket
        """

        # extract current time
        return int(SimulationTimeConverter.convert_to_temporal_bucket(self._time.now(), self._temporal_resolution))
