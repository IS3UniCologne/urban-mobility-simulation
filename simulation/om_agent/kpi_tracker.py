import os
import sys
import logging
import pandas as pd
from simulation.helper.configuration.configuration import Configuration
from simulation.vehicle.vehicle import VehicleState


class KPITracker:
    __instance = None

    def __init__(self, extraction_interval=60):

        self._results_path = os.path.join(os.getcwd(), "simulation", "om_agent", "results", "kpi_tracker_results.csv")
        self._car_agent_behaviour_results_path = os.path.join(os.getcwd(), "simulation", "om_agent", "results", "car_agent_behaviour_results.csv")
        self._scooter_agent_behaviour_results_path = os.path.join(os.getcwd(), "simulation", "om_agent", "results",
                                                         "scooter_agent_behaviour_results.csv")
        self._kickscooter_agent_behaviour_results_path = os.path.join(os.getcwd(), "simulation", "om_agent", "results",
                                                         "kickscooter_agent_behaviour_results.csv")
        self._results_df = pd.DataFrame()
        self._env = None
        self._mixed_fleet = None
        self._recharge_threshold = Configuration.instance().shared_vehicle_operator_config.recharge_threshold

        # threshold when vehicles "risk" to get stuck /not used anymore...
        self._critical_soc_threshold = Configuration.instance().shared_vehicle_operator_config.critical_soc_threshold

        self._extraction_interval = extraction_interval
        self._episode = 0
        self._car_agent_reward_sum = 0
        self._scooter_agent_reward_sum = 0
        self._kickscooter_agent_reward_sum = 0

        self._car_charging_sum = 0
        self._scooter_charging_sum = 0
        self._kickscooter_charging_sum = 0

        self._car_actions = 0.0001
        self._scooter_actions = 0.0001
        self._kickscooter_actions = 0.0001


        self._unique_hex_ids = Configuration.instance().get_hex_id_list()

        #{"A": {"A": 0.15, "B": 1.23}, "B": {"A": 0.98, "B": 1.45}}
        self._car_hexagon_soc_trips = {origin: {destination: [0.0,0] for destination in self._unique_hex_ids}for origin in self._unique_hex_ids}
        self._scooter_hexagon_soc_trips = {origin: {destination: [0.0,0] for destination in self._unique_hex_ids}for origin in self._unique_hex_ids}
        self._kickscooter_hexagon_soc_trips = {origin: {destination: [0.0,0] for destination in self._unique_hex_ids}for origin in self._unique_hex_ids}


        self._charging_relocation_duration = 0
        self._charging_relocation_distance = 0

        self.maximum_queue_length_cars = 0
        self.maximum_queue_length_scooters = 0
        self.maximum_queue_length_kickscooters = 0

        self.number_of_charging_vehicles_cars = 0
        self.number_of_charging_vehicles_scooters = 0
        self.number_of_charging_vehicles_kickscooters = 0

        self.charging_agent_active_episodes = 0

        #fake singleton
        KPITracker.__instance = self

    def increase_charging_agent_active_episodes(self):
        self.charging_agent_active_episodes += 1

    @staticmethod
    def instance() -> 'KPITracker':
        """ Static access method. """
        if KPITracker.__instance is None:
            raise Exception("World was not initialized")
        else:
            return KPITracker.__instance

    def run(self):

        while True:

            # extract SOC KPIs
            number_of_vehicles_below_critical_soc_treshold_car = 0
            number_of_vehicles_below_critical_soc_treshold_scooter = 0
            number_of_vehicles_below_critical_soc_treshold_kickscooter = 0
            sum_soc_car = 0
            sum_soc_scooter = 0
            sum_soc_kickscooter = 0

            # cars
            for car in self.mixed_fleet.cars:
                soc = car.current_state_of_charge
                sum_soc_car += soc
                if soc < (self._critical_soc_threshold * car.max_state_of_charge):
                    number_of_vehicles_below_critical_soc_treshold_car += 1

            # scooter
            for scooter in self.mixed_fleet.scooters:
                soc = scooter.current_state_of_charge
                sum_soc_scooter += soc
                if soc < (self._critical_soc_threshold * scooter.max_state_of_charge):
                    number_of_vehicles_below_critical_soc_treshold_scooter += 1

            # kickscooter
            for kickscooter in self.mixed_fleet.kickscooters:
                soc = kickscooter.current_state_of_charge
                sum_soc_kickscooter += soc
                if soc < (self._critical_soc_threshold * kickscooter.max_state_of_charge):
                    number_of_vehicles_below_critical_soc_treshold_kickscooter += 1

            # add results to dataframe and save to csv
            self._results_df = pd.concat([self.results_df, pd.DataFrame(
                {'episode': [self._episode],
                 'env_time': [self.env.now],
                 'number_of_vehicles_below_critical_soc_treshold_car': [number_of_vehicles_below_critical_soc_treshold_car],
                 'number_of_vehicles_below_critical_soc_treshold_scooter': [
                     number_of_vehicles_below_critical_soc_treshold_scooter],
                 'number_of_vehicles_below_critical_soc_treshold_kickscooter': [
                     number_of_vehicles_below_critical_soc_treshold_kickscooter],
                 'sum_soc_car': [sum_soc_car],
                 'sum_soc_scooter': [sum_soc_scooter],
                 'sum_soc_kickscooter': [sum_soc_kickscooter],
                 'number_of_charging_vehicles_car': [self.number_of_charging_vehicles_cars],
                 'number_of_charging_vehicles_scooter': [self.number_of_charging_vehicles_scooters],
                 'number_of_charging_vehicles_kickscooter': [self.number_of_charging_vehicles_kickscooters],
                 'avg_car_agent_reward_sum' : [self._car_agent_reward_sum / self._car_actions],
                 'avg_scooter_agent_reward_sum' : [self._scooter_agent_reward_sum / self._scooter_actions],
                 'avg_kickscooter_agent_reward_sum': [self._kickscooter_agent_reward_sum / self._kickscooter_actions],
                 'car_charging_sum': [self._car_charging_sum],
                 'scooter_charging_sum': [self._scooter_charging_sum],
                 'kickscooter_charging_sum': [self._kickscooter_charging_sum],
                 'maximum_queue_length_cars': [self.maximum_queue_length_cars],
                 'maximum_queue_length_scooters': [self.maximum_queue_length_scooters],
                 'maximum_queue_length_kickscooters': [self.maximum_queue_length_kickscooters]
                 })], axis=0)

            self.results_df.to_csv(self._results_path)

            # reset agents rewards
            self._car_agent_reward_sum = 0
            self._scooter_agent_reward_sum = 0
            self._kickscooter_agent_reward_sum = 0

            self._car_actions = 0.0001
            self._scooter_actions = 0.0001
            self._kickscooter_actions = 0.0001


            # reset charging amount
            self._car_charging_sum = 0
            self._scooter_charging_sum = 0
            self._kickscooter_charging_sum = 0

            # reset queue length
            self.maximum_queue_length_cars = 0
            self.maximum_queue_length_scooters = 0
            self.maximum_queue_length_kickscooters = 0

            self.number_of_charging_vehicles_cars = 0
            self.number_of_charging_vehicles_scooters = 0
            self.number_of_charging_vehicles_kickscooters = 0

            # wait e.g. 60 minutes
            yield self._env.timeout(self.extraction_interval)

    def track_maximum_queue_length(self, no_waiting_vehicles, vehicle_type):

        if vehicle_type == "SharedCar":
            if no_waiting_vehicles > self.maximum_queue_length_cars:
                self.maximum_queue_length_cars = no_waiting_vehicles
        elif vehicle_type == "SharedScooter":
            if no_waiting_vehicles > self.maximum_queue_length_scooters:
                self.maximum_queue_length_scooters = no_waiting_vehicles
        elif vehicle_type == "SharedKickscooter":
            if no_waiting_vehicles > self.maximum_queue_length_kickscooters:
                self.maximum_queue_length_kickscooters = no_waiting_vehicles
        else:
            logging.error("Vehicle type not found")
            sys.exit(-1)


    def execute_soc_origin_destination_tracking(self, user, selected_vehicle, vehicle_type):
        """
        Track SOC and number of trips for each vehicle type and the origin destination
        combination.
        :param user:
        :param selected_vehicle:
        :return:
        """


        origin = user.transport_task.origin.get_default_hexagon()
        destination = user.transport_task.destination.get_default_hexagon()


        # check vehicle type
        if vehicle_type == 'SharedCar':
            self._car_hexagon_soc_trips[origin][destination][0] += selected_vehicle.current_relative_state_of_charge
            self._car_hexagon_soc_trips[origin][destination][1] += 1
        elif vehicle_type == 'SharedScooter':
            self._scooter_hexagon_soc_trips[origin][destination][0] += selected_vehicle.current_relative_state_of_charge
            self._scooter_hexagon_soc_trips[origin][destination][1] += 1
        elif vehicle_type == 'SharedKickscooter':
            self._kickscooter_hexagon_soc_trips[origin][destination][0] += selected_vehicle.current_relative_state_of_charge
            self._kickscooter_hexagon_soc_trips[origin][destination][1] += 1
        else:
            print('Vehicle Type in kpi_tracker not found')
            sys.exit(1)


    def store_and_reset_agent_behaviour_results(self):
        #compute average
        # {"A": {"A": [0.15,1] "B": [1.23,1]}, "B": {"A": [0.98,1], "B": [1.45,1]}}

        dict_cars_soc = {origin_key:{destination_key: destination_value[0]/destination_value[1] if
            destination_value[1] != 0 else 0 for destination_key,destination_value in origin_value.items()}
                         for origin_key,origin_value in self._car_hexagon_soc_trips.items()}

        dict_scooters_soc = {origin_key: {
            destination_key: destination_value[0] / destination_value[1] if destination_value[1] != 0 else 0 for
            destination_key, destination_value in origin_value.items()} for origin_key, origin_value in
                         self._scooter_hexagon_soc_trips.items()}

        dict_kickscooters_soc = {origin_key: {
            destination_key: destination_value[0] / destination_value[1] if destination_value[1] != 0 else 0 for
            destination_key, destination_value in origin_value.items()} for origin_key, origin_value in
                         self._kickscooter_hexagon_soc_trips.items()}

        df_cars = pd.DataFrame.from_dict(dict_cars_soc)
        df_scooters = pd.DataFrame.from_dict(dict_scooters_soc)
        df_kickscooters = pd.DataFrame.from_dict(dict_kickscooters_soc)

        #save to csv
        df_cars.to_csv(self._car_agent_behaviour_results_path)
        df_scooters.to_csv(self._scooter_agent_behaviour_results_path)
        df_kickscooters.to_csv(self._kickscooter_agent_behaviour_results_path)

        # reset attributes
        self._car_hexagon_soc_trips = {origin: {destination: [0.0,0] for destination in self._unique_hex_ids}for origin in self._unique_hex_ids}
        self._scooter_hexagon_soc_trips = {origin: {destination: [0.0,0] for destination in self._unique_hex_ids}for origin in self._unique_hex_ids}
        self._kickscooter_hexagon_soc_trips = {origin: {destination: [0.0,0] for destination in self._unique_hex_ids}for origin in self._unique_hex_ids}

    def increase_relocation_distance(self,distance):
        self._charging_relocation_distance += distance


    def increase_relocation_duration_time(self, duration):
        self._charging_relocation_duration += duration


    def reset_relocation_distance_and_duration_tracking(self):
        self._charging_relocation_duration = 0
        self._charging_relocation_distance = 0

    def increase_number_of_charging_vehicles(self, vehicle_type):

        if vehicle_type == "SharedCar":
            self.number_of_charging_vehicles_cars += 1
        elif vehicle_type == "SharedScooter":
            self.number_of_charging_vehicles_scooters += 1
        elif vehicle_type == "SharedKickscooter":
            self.number_of_charging_vehicles_kickscooters += 1
        else:
            logging.error(f"Vehicle type {vehicle_type} not found.")
            sys.exit(-1)


    @property
    def charging_relocation_distance(self):
        return self._charging_relocation_distance

    @property
    def charging_relocation_duration(self):
        return self._charging_relocation_duration

    @property
    def mixed_fleet(self):
        return self._mixed_fleet

    @property
    def env(self):
        return self._env

    @env.setter
    def env(self, env):
        self._env = env

    @mixed_fleet.setter
    def mixed_fleet(self, mixed_fleet):
        self._mixed_fleet = mixed_fleet

    @property
    def recharge_threshold(self):
        return self._recharge_threshold

    @property
    def results_df(self):
        return self._results_df

    @property
    def results_path(self):
        return self._results_df

    @property
    def extraction_interval(self):
        return self._extraction_interval

    def increase_episode(self):
        self._episode += 1

    @property
    def car_agent_reward_sum(self):
        return self._car_agent_reward_sum

    def increase_car_agent_reward_sum(self, reward):
        self._car_actions += 1
        self._car_agent_reward_sum += reward

    @property
    def scooter_agent_reward_sum(self):
        return self._scooter_agent_reward_sum

    def increase_scooter_agent_reward_sum(self, reward):
        self._scooter_actions += 1
        self._scooter_agent_reward_sum += reward

    @property
    def kickscooter_agent_reward_sum(self):
        return self._kickscooter_agent_reward_sum

    def increase_kickscooter_agent_reward_sum(self, reward):
        self._kickscooter_actions += 1
        self._kickscooter_agent_reward_sum += reward

    @property
    def car_charging_sum(self):
        return self._car_charging_sum

    def increase_car_charging_sum(self, reward):
        self._car_charging_sum += reward

    @property
    def scooter_charging_sum(self):
        return self._scooter_charging_sum

    def increase_scooter_charging_sum(self, reward):
        self._scooter_charging_sum += reward

    @property
    def kickscooter_charging_sum(self):
        return self._kickscooter_charging_sum

    def increase_kickscooter_charging_sum(self, reward):
        self._kickscooter_charging_sum += reward