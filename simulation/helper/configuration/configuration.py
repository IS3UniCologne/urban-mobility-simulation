from enum import Enum
import numpy as np


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
            Configuration(spatial_resolution=7, temporal_resolution=4)
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
        self._output_path = ''
        self._transaction_file = ''
        self._fleet_state_file = ''

        self._vehicle_configs = {}

        self._mode_choice_config = []

        self._user_config = None

        # [cst, price, waiting_time, EV, trip_duration, trust_AV, trust_HV, cst_AV, cst_HV]
        MoD_coefficients = np.array([[-0.273671504, -0.353911557, -0.103573505, -1.128132785, 0.150429623,
                                            -0.576113819, 7.297866296, 0.631438368, -1.011643365],
                                           [-0.318885388, -1.281672341, -0.454985255, 0.123860882, 1.060810562,
                                            5.74223911, 12.76153448, 0.579730247, -0.746119133],
                                           [-0.529871517, -0.176603082, -0.624049182, -0.094335042, -0.07608058,
                                            6.357501057, 3.73756425, 1.017193094, 1.048363966],
                                           [0.00, -0.228709544, -0.161649449, -0.069096605, 0.133775179, -0.802892154,
                                            7.325820705, 0.729678667, -0.735175789]])  # TODO: read it from a dataet
        self._MoD_p_values = np.array([[0.00, 0.03, 0.00, 0.00, 0.42, 0.00, 0.00, 0.00, 0.18],
                                       [0.00, 0.00, 0.73, 0.01, 0.08, 0.00, 0.13, 0.14, 0.10],
                                       [0.02, 0.00, 0.82, 0.25, 0.00, 0.02, 0.00, 0.00, 0.01],
                                       [0.00, 0.00, 0.70, 0.00, 0.39, 0.00, 0.00, 0.00, 0.00]])
        MoD_significant = self._MoD_p_values.copy()
        MoD_significant[MoD_significant <= 0.2] = 1
        MoD_significant[MoD_significant != 1] = 0

        self._MoD_coefficients = MoD_coefficients * MoD_significant

        self._shared_vehicle_operator_config = None

        self._charging_infrastructure_config = None

        self._recharging_threshold = None

        self._add_driver_availability_vector = None

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

    def add_ride_hailing_info(self, driver_payment_share):
        self._driver_payment_share = driver_payment_share

    def get_driver_payment_share(self):
        return self._driver_payment_share

    def get_distance_threshold_to_user(self):
        return 10000

    def get_AV_price_reduction(self):
        return 0.9

    def add_tech_penetration(self, EV_penetration, AV_penetration):
        self._EV_penetration = EV_penetration
        self._AV_penetration = AV_penetration

    def get_EV_penetration(self):
        return self._EV_penetration

    def get_AV_penetration(self):
        return self._AV_penetration

    def get_driver_availability_vector(self):
        return self._add_driver_availability_vector

    def add_driver_availability_vector(self, availability_vector):
        self._add_driver_availability_vector = availability_vector

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

    @property
    def MoD_coefficients(self):
        return self._MoD_coefficients

    def add_shared_vehicle_operator_config(self, shared_mobility_ops_config):
        self._shared_vehicle_operator_config = shared_mobility_ops_config

    def add_charging_infrastructure_config(self, charging_infrastructure_ops_config):
        self._charging_infrastructure_config = charging_infrastructure_ops_config

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

    def add_recharging_threshold(self, values):
        self._recharging_threshold = values

    def get_recharging_threshold(self):
        return self._recharging_threshold


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

        self.substitution_boundary = substitution_boundary
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


class ChargingInfrastructureConfig:
    def __init__(self, location, power, capacity):
        self.location = location
        self.power = power
        self.capacity = capacity


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
