from enum import Enum


class TemporalBucket(Enum):
    HOURLY_BUCKETS = 1
    TWO_HOURLY_BUCKETS = 2
    FOUR_HOURLY_BUCKETS = 4
    SIX_HOURLY_BUCKETS = 6
    EIGHT_HOURLY_BUCKETS = 8
    TWELVE_HOURLY_BUCKETS = 12

class DailyResolution(Enum):
    DAILY = 0
    WEEKDAY_WEEKEND = 1
    NONE = 2

class SpatialResolution(Enum):
    HEX_7 = 7
    HEX_8 = 8
    HEX_9 = 9

class ModeChoiceStrategy(Enum):
    RANDOM = 0
    SUBSTITUTION_AWARE = 1
    NO_SUBSTITUTION = 2

class Configuration:
    # There is only one instance of this class.
    __instance = None

    @staticmethod
    def instance() -> 'Configuration':
        """ Static access method. """
        if Configuration.__instance == None:
            Configuration(spatial_resolution = 7, temporal_resolution = 4)
        return Configuration.__instance

    @staticmethod
    def init(spatial_resolution, temporal_resolution, daily_resolution):
        """ Static access method. """
        if Configuration.__instance == None:
            Configuration(spatial_resolution, temporal_resolution, daily_resolution)
        return Configuration.__instance

    def __init__(self, spatial_resolution: int, temporal_resolution: int, daily_resolution: int):
        """ Virtually private constructor. """
        if Configuration.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            Configuration.__instance = self
            super(Configuration, self).__init__()

        self._spatial_resolution = SpatialResolution(spatial_resolution)
        self._temporal_resolution = TemporalBucket(temporal_resolution)
        self._daily_resolution = DailyResolution(daily_resolution)

        self._store_results = False
        self._output_path   = ''
        self._transaction_file = ''
        self._fleet_state_file = ''

        self._vehicle_configs = {}

        self._mode_choice_config = []

        self._user_config = None

        self._shared_vehicle_operator_config = None

        self._transit_operator_config = None

        self._transit_agent_config = None

    @property
    def spatial_resolution(self):
        return self._spatial_resolution

    @property
    def spatial_resolution_value(self):
        return self._spatial_resolution.value

    @property
    def temporal_resolution(self):
        return self._temporal_resolution

    @property
    def spatial_resolution_column(self):
        return f"hex_id_{self.spatial_resolution_value}"

    @property
    def daily_resolution(self):
        return self._daily_resolution

    @property
    def store_results(self):
        return self._store_results

    @property
    def output_path(self):
        return self._output_path

    @property
    def transaction_file(self):
        return self._transaction_file

    @property
    def fleet_state_file(self):
        return self._fleet_state_file

    def add_vehicle_config(self, vehicle_type_name, vehicle_config):
        self._vehicle_configs[vehicle_type_name] = vehicle_config

    def get_vehicle_config(self, vehicle_type_name):
        return self._vehicle_configs[vehicle_type_name]

    def add_mode_choice_config(self, mode_choice_config):
        self._mode_choice_config = mode_choice_config

    def get_mode_choice_config(self):
        return self._mode_choice_config

    def add_user_config(self, user_config):
        self._user_config = user_config

    @property
    def user_config(self):
        return self._user_config

    def add_shared_vehicle_operator_config(self, shared_mobility_ops_config):
        self._shared_vehicle_operator_config = shared_mobility_ops_config

    @property
    def shared_vehicle_operator_config(self):
        return self._shared_vehicle_operator_config

    def add_transit_operator_config(self, transit_operator_config):
        self._transit_operator_config = transit_operator_config

    @property
    def transit_operator_config(self):
        return self._transit_operator_config

    def add_transit_agent_config(self, transit_agent_config):
        self._transit_agent_config = transit_agent_config

    @property
    def transit_agent_config(self):
        return self._transit_agent_config

    def set_store_results(self, store_results):
        self._store_results = store_results

    def set_output_path(self, path):
        self._output_path = path

    def set_transaction_file(self, file):
        self._transaction_file = file

    def set_fleet_state_file(self, file):
        self._fleet_state_file = file

    def get_available_vehicle_types(self):
        return list(self._vehicle_configs.keys())


class VehicleConfig:
    def __init__(self, price_per_min, max_state_of_charge, energy_consumption,
                 velocity, max_available_seats, max_walking_distance, daily_total_cost):
        self.price_per_min = price_per_min
        self.max_state_of_charge = max_state_of_charge
        self.energy_consumption = energy_consumption
        self.velocity = velocity
        self.max_available_seats = max_available_seats
        self.max_walking_distance = max_walking_distance
        self.daily_total_cost = daily_total_cost


class ModeChoiceConfig:
    def __init__(self, mode_choice_strategy, substitution_boundary, available_modes, path_to_model):
        if mode_choice_strategy == "random":
            self.mode_choice_strategy = ModeChoiceStrategy.RANDOM
        elif mode_choice_strategy == "substitution":
            self.mode_choice_strategy = ModeChoiceStrategy.SUBSTITUTION_AWARE
        elif mode_choice_strategy == "no_sub":
            self.mode_choice_strategy = ModeChoiceStrategy.NO_SUBSTITUTION

        self.substitution_boundary  = substitution_boundary
        self.available_modes = available_modes
        self.path_to_model = path_to_model


class UserConfig:
    def __init__(self, spatial_strategy, max_wait):
        self.spatial_strategy = spatial_strategy
        self.max_wait = int(max_wait)

class SharedVehicleOperatorConfig:
    def __init__(self, recharge_threshold, charging_station_power, number_of_service_worker,
                 base_regions, base_capacity, operations_start, operations_duration, vehicle_relocation_velocity):
        self.recharge_threshold = recharge_threshold
        self.charging_station_power = charging_station_power
        self.number_of_service_worker = number_of_service_worker
        self.base_regions = base_regions
        self.base_capacity = base_capacity
        self.operations_start = operations_start
        self.operations_duration = operations_duration
        self.vehicle_relocation_velocity = vehicle_relocation_velocity

class TransitOperatorConfig:
    def __init__(self, planning_lookahead, max_busses):
        self.planning_lookahead = int(planning_lookahead)
        self.max_busses = int(max_busses)


class TransitAgentConfig:
    def __init__(self, action_resolution, alpha, eps, gamma, n):
        self.action_resolution = int(action_resolution)
        self.alpha = float(alpha)
        self.eps = float(eps)
        self.gamma = float(gamma)
        self.n = int(n)
