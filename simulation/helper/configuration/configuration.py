import random
from enum import Enum
from typing import Deque, Optional, Union

import numpy as np

# from keras.callbacks import TensorBoard
from learning.spaces.action_space import DiscreteActionSpace


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
    def instance() -> "Configuration":
        """Static access method."""
        if Configuration.__instance is None:
            Configuration(
                spatial_resolution=7,
                temporal_resolution=4,
                daily_resolution=1,
                city="berlin",
            )
        return Configuration.__instance

    @staticmethod
    def init(spatial_resolution, temporal_resolution, daily_resolution, city):
        """Static access method."""
        if Configuration.__instance is None:
            Configuration(
                spatial_resolution, temporal_resolution, daily_resolution, city
            )
        return Configuration.__instance

    def __init__(
        self,
        spatial_resolution: int,
        temporal_resolution: int,
        daily_resolution: int,
        city: str,
    ):
        """Virtually private constructor."""
        if Configuration.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Configuration.__instance = self
            super(Configuration, self).__init__()

        self._spatial_resolution = SpatialResolution(spatial_resolution)
        self._temporal_resolution = TemporalBucket(temporal_resolution)
        self._daily_resolution = DailyResolution(daily_resolution)
        self._city = city

        self._store_results = False
        self._output_path = ""
        self._transaction_file = ""
        self._fleet_state_file = ""

        self._shared_vehicle_configs = {}

        self._mode_choice_config = []

        self._user_config = None

        self._ridehailing_vehicle_configs = {}

        # [cst, price, waiting_time, EV, trip_duration, cst_AV, cst_HV, trust_AV, trust_HV]
        MoD_coefficients = np.array(
            [
                [
                    -0.273671504,
                    -0.353911557,
                    -0.103573505,
                    -1.128132785,
                    0.150429623,
                    -0.576113819,
                    7.297866296,
                    0.631438368,
                    -1.011643365,
                ],
                [
                    -0.318885388,
                    -1.281672341,
                    -0.454985255,
                    0.123860882,
                    1.060810562,
                    5.74223911,
                    12.76153448,
                    0.579730247,
                    -0.746119133,
                ],
                [
                    -0.529871517,
                    -0.176603082,
                    -0.624049182,
                    -0.094335042,
                    -0.07608058,
                    6.357501057,
                    3.73756425,
                    1.017193094,
                    1.048363966,
                ],
                [
                    0.00,
                    -0.228709544,
                    -0.161649449,
                    -0.069096605,
                    0.133775179,
                    -0.802892154,
                    7.325820705,
                    0.729678667,
                    -0.735175789,
                ],
            ]
        )  # TODO: read it from a dataet
        self._MoD_coefficients_ci_lower = np.array(
            [
                [-0.670, -0.463, -0.198, -1.721, 0.083, -1.960, 5.347, 0.409, -1.415],
                [-0.695, -1.702, -0.601, -0.588, 0.278, -0.573, 6.894, -0.175, -1.747],
                [-0.941, -0.320, -0.805, -0.917, -0.205, 3.597, 0.648, 0.498, 0.447],
                [0.000, -0.307, -0.237, -0.425, 0.068, -2.626, 5.734, 0.330, -1.036],
            ]
        )
        self._MoD_coefficients_ci_upper = np.array(
            [
                [0.122, -0.245, -0.009, -0.535, 0.218, 0.808, 9.248, 0.853, -0.608],
                [0.057, -0.862, -0.309, 0.835, 1.844, 12.057, 18.629, 1.335, 0.254],
                [-0.119, -0.033, -0.443, 0.729, 0.053, 9.118, 6.827, 1.537, 1.650],
                [0.000, -0.150, -0.086, 0.286, 0.199, 1.019, 8.917, 1.129, -0.434],
            ]
        )
        self._MoD_p_values = np.array(
            [
                [0.00, 0.03, 0.00, 0.00, 0.42, 0.00, 0.00, 0.00, 0.18],
                [0.00, 0.00, 0.73, 0.01, 0.08, 0.00, 0.13, 0.14, 0.10],
                [0.02, 0.00, 0.82, 0.25, 0.00, 0.02, 0.00, 0.00, 0.01],
                [0.00, 0.00, 0.70, 0.00, 0.39, 0.00, 0.00, 0.00, 0.00],
            ]
        )
        MoD_significant = self._MoD_p_values.copy()

        MoD_significant[MoD_significant <= 0.2] = 1
        MoD_significant[MoD_significant != 1] = 1

        self._MoD_coefficients = MoD_coefficients * MoD_significant

        self._MoD_coefficient_interval_adjuster = None

        self._AV_trust = None

        self._shared_vehicle_operator_config = None

        self._ridehailing_operator_config = None

        self._population_config = None

        self._charging_infrastructure_config = None

        self._recharging_threshold = None

        self._add_driver_availability_vector = None

        self._transit_operator_config = None

        self._transit_agent_config = None

        self._bus_config = None

        self.dynamic_routing_config = None

        self.dynamic_checkpoint_routing_config = None

        self._DQN_config = None

        self._distance_threshold_to_user = None

        self._driver_payment_share = None

        self._AV_price_reduction = None

        self._price_params = None

        self._distance_threshold_to_user = None

        self._driver_payment_share = None

        self._AV_price_reduction = None

        self._price_params = None

    @property
    def spatial_resolution(self):
        return self._spatial_resolution

    @spatial_resolution.setter
    def spatial_resolution(self, spatial_resolution: int):
        self._spatial_resolution = SpatialResolution(spatial_resolution)

    @property
    def city(self):
        return self._city

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

    def add_ride_hailing_info(
        self, driver_payment_share, AV_price_reduction, price_params
    ):
        self._driver_payment_share = driver_payment_share
        self._AV_price_reduction = AV_price_reduction
        self._price_params = price_params

    def get_driver_payment_share(self):
        return self._driver_payment_share

    def add_distance_threshold_to_user(self, distance):
        self._distance_threshold_to_user = distance

    def get_distance_threshold_to_user(self):
        return self._distance_threshold_to_user

    def get_AV_price_reduction(self):
        return self._AV_price_reduction

    def get_price_parameters_ride_hailing(self):
        return self._price_params

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

    def add_shared_vehicle_config(self, vehicle_type_name, shared_vehicle_config):
        self._shared_vehicle_configs[vehicle_type_name] = shared_vehicle_config

    def get_shared_vehicle_config(self, vehicle_type_name):
        return self._shared_vehicle_configs[vehicle_type_name]

    def add_ridehailing_vehicle_config(
        self, vehicle_type_name, ridehailing_vehicle_config
    ):
        self._ridehailing_vehicle_configs[vehicle_type_name] = (
            ridehailing_vehicle_config
        )

    def get_ridehailing_vehicle_config(self, vehicle_type_name):
        return self._ridehailing_vehicle_configs[vehicle_type_name]

    def add_mode_choice_config(self, mode_choice_config):
        self._mode_choice_config = mode_choice_config

    def get_mode_choice_config(self):
        return self._mode_choice_config

    def add_user_config(self, user_config):
        self._user_config = user_config

    def generate_mode_choice_coefficient(self, pop_value):
        mode_choice_coefficients_ci_lower = self.ci_lower_MoD_coefficients[pop_value]
        mode_choice_coefficients_ci_upper = self.ci_upper_MoD_coefficients[pop_value]
        interval_adjuster = self.MoD_coefficient_interval_adjuster
        adjuster = (
            (mode_choice_coefficients_ci_upper - mode_choice_coefficients_ci_lower)
            / 2
            * interval_adjuster
        )
        mode_choice_coefficients_ci_lower = mode_choice_coefficients_ci_lower + adjuster
        mode_choice_coefficients_ci_upper = mode_choice_coefficients_ci_upper - adjuster
        mode_choice_coefficients = random.uniform(
            mode_choice_coefficients_ci_lower, mode_choice_coefficients_ci_upper
        )
        return mode_choice_coefficients

    def generate_AV_trust(self, pop_value):
        trust_value_lower = self.AV_trust[pop_value] - 0.5
        trust_value_upper = self.AV_trust[pop_value] + 0.5
        trust_value = random.uniform(trust_value_lower, trust_value_upper)
        return trust_value

    @property
    def user_config(self):
        return self._user_config

    @property
    def MoD_coefficients(self):
        return self._MoD_coefficients

    @property
    def ci_lower_MoD_coefficients(self):
        return self._MoD_coefficients_ci_lower

    @property
    def ci_upper_MoD_coefficients(self):
        return self._MoD_coefficients_ci_upper

    @property
    def MoD_coefficient_interval_adjuster(self):
        return self._MoD_coefficient_interval_adjuster

    @property
    def AV_trust(self):
        return self._AV_trust

    def add_AV_trust(self, AV_trust):
        self._AV_trust = np.array(AV_trust)

    def add_MoD_coefficient_interval_adjuster(self, MoD_coefficient_interval_adjuster):
        self._MoD_coefficient_interval_adjuster = MoD_coefficient_interval_adjuster

    def add_shared_vehicle_operator_config(
        self, shared_mobility_ops_config: "SharedVehicleOperatorConfig"
    ):
        self._shared_vehicle_operator_config = shared_mobility_ops_config

    def add_ridehailing_operator_config(
        self, ridehailing_ops_config: "RideHailingOperatorConfig"
    ):
        self._ridehailing_operator_config = ridehailing_ops_config

    def add_charging_infrastructure_config(self, charging_infrastructure_ops_config):
        self._charging_infrastructure_config = charging_infrastructure_ops_config

    def add_population_config(self, population_config):
        self._population_config = population_config

    @property
    def shared_vehicle_operator_config(self):
        return self._shared_vehicle_operator_config

    @property
    def ridehailing_operator_config(self):
        return self._ridehailing_operator_config

    def add_transit_operator_config(
        self, transit_operator_config: "TransitOperatorConfig"
    ):
        self._transit_operator_config = transit_operator_config

    @property
    def transit_operator_config(self):
        return self._transit_operator_config

    def add_bus_config(self, bus_config):
        self._bus_config = bus_config

    @property
    def bus_config(self):
        return self._bus_config

    def add_dynamic_routing_config(self, dynamic_routing_config):
        self.dynamic_routing_config = dynamic_routing_config

    # @property
    # def dynamic_routing_config(self):
    #     return self._dynamic_routing_config

    def add_dynamic_checkpoint_routing_config(self, dynamic_checkpoint_routing_config):
        self.dynamic_checkpoint_routing_config = dynamic_checkpoint_routing_config

    # TODO: somehow setting attributes this way didn't work but it works for DQN?
    # @property
    # def dynamic_checkpoint_routing_config(self):
    #     return self._dynamic_checkpoint_routing_config
    #
    def add_DQN_config(self, DQN_config):
        self._DQN_config = DQN_config

    @property
    def DQN_config(self):
        return self._DQN_config

    def set_store_results(self, store_results):
        self._store_results = store_results

    def set_output_path(self, path):
        self._output_path = path

    def set_transaction_file(self, file):
        self._transaction_file = file

    def set_fleet_state_file(self, file):
        self._fleet_state_file = file

    def get_available_shared_vehicle_types(self):
        return list(self._shared_vehicle_configs.keys())

    def get_available_ridehailing_vehicle_types(self):
        return list(self._ridehailing_vehicle_configs.keys())

    @property
    def MoD_coefficients_ci_lower(self):
        return self._MoD_coefficients_ci_lower

    @property
    def MoD_coefficients_ci_upper(self):
        return self._MoD_coefficients_ci_upper


class SharedVehicleConfig:
    def __init__(
        self,
        price_per_min,
        max_state_of_charge,
        energy_consumption,
        velocity,
        max_available_seats,
        max_walking_distance,
        daily_total_cost,
        initial_SoC,
        EV_relative_energy_consumption,
        cost_per_km,
        charging_cost_per_kWh,
    ):
        self.price_per_min = price_per_min
        self.max_state_of_charge = max_state_of_charge
        self.energy_consumption = energy_consumption
        self.velocity = velocity
        self.max_available_seats = max_available_seats
        # TODO: move max_walking_distance to UserConfig?
        self.max_walking_distance = max_walking_distance
        self.daily_total_cost = daily_total_cost
        self.initial_SoC = initial_SoC
        self.EV_relative_energy_consumption = EV_relative_energy_consumption
        self.cost_per_km = cost_per_km
        self.charging_cost_per_kWh = charging_cost_per_kWh


class RideHailingVehicleConfig:
    def __init__(
        self,
        price_per_min,
        max_state_of_charge,
        energy_consumption,
        velocity,
        max_available_seats,
        initial_SoC,
        charging_cost_per_kWh,
        cost_per_km,
        EV_relative_energy_consumption,
    ):
        self.price_per_min = price_per_min
        self.max_state_of_charge = max_state_of_charge
        self.energy_consumption = energy_consumption
        self.velocity = velocity
        self.max_available_seats = max_available_seats
        self.initial_SoC = initial_SoC
        self.charging_cost_per_kWh = charging_cost_per_kWh
        self.cost_per_km = cost_per_km
        self.EV_relative_energy_consumption = EV_relative_energy_consumption


class ModeChoiceConfig:
    def __init__(self, mode_choice_strategy, substitution_boundary, path_to_model):
        if mode_choice_strategy == "random":
            self.mode_choice_strategy = ModeChoiceStrategy.RANDOM
        elif mode_choice_strategy == "substitution":
            self.mode_choice_strategy = ModeChoiceStrategy.SUBSTITUTION_AWARE
        elif mode_choice_strategy == "no_sub":
            self.mode_choice_strategy = ModeChoiceStrategy.NO_SUBSTITUTION

        self.substitution_boundary = substitution_boundary
        self.path_to_model = path_to_model


class PopulationConfig:
    def __init__(self, population_probabilities, type_paths):
        self.population_probabilities = population_probabilities
        self.type_paths = type_paths


class UserConfig:
    def __init__(self, spatial_strategy: str, max_wait: int):
        self.spatial_strategy = spatial_strategy
        self.max_wait = int(max_wait)


class RideHailingOperatorConfig:
    def __init__(
        self,
        recharge_threshold,
        charging_station_power,
        number_of_service_worker,
        base_regions,
        base_capacity,
        operations_start,
        operations_duration,
        vehicle_relocation_velocity,
        available_modes,
        available_modes_supply,
        n_autonomous_cars,
        n_ridehailing_cars,
        allocation,
    ):
        self.recharge_threshold = recharge_threshold
        self.charging_station_power = charging_station_power
        self.number_of_service_workers = number_of_service_worker
        self.base_regions = base_regions
        self.base_capacity = base_capacity
        self.operations_start = operations_start
        self.operations_duration = operations_duration
        self.vehicle_relocation_velocity = vehicle_relocation_velocity
        self.available_modes = available_modes
        self.available_modes_supply = available_modes_supply
        self.n_autonomous_cars = n_autonomous_cars
        self.n_ridehailing_cars = n_ridehailing_cars
        self.allocation = allocation


class SharedVehicleOperatorConfig:
    def __init__(
        self,
        recharge_threshold,
        charging_station_power,
        number_of_service_worker,
        base_regions,
        base_capacity,
        operations_start,
        operations_duration,
        vehicle_relocation_velocity,
        available_modes,
        available_modes_supply,
        n_cars,
        n_scooters,
        n_kickscooters,
        n_bikes,
    ):
        self.recharge_threshold = recharge_threshold
        self.charging_station_power = charging_station_power
        self.number_of_service_workers = number_of_service_worker
        self.base_regions = base_regions
        self.base_capacity = base_capacity
        self.operations_start = operations_start
        self.operations_duration = operations_duration
        self.vehicle_relocation_velocity = vehicle_relocation_velocity
        self.available_modes = available_modes
        self.available_modes_supply = available_modes_supply
        self.n_cars = n_cars
        self.n_scooters = n_scooters
        self.n_kickscooters = n_kickscooters
        self.n_bikes = n_bikes


class ChargingInfrastructureConfig:
    def __init__(self, location, power, capacity):
        self.location = location
        self.power = power
        self.capacity = capacity


class TransitOperatorConfig:
    def __init__(self, planning_lookahead: int, max_busses: int):
        self.planning_lookahead = planning_lookahead
        self.max_busses = max_busses


class BusConfig:
    def __init__(self, velocity: float, max_available_seats: int):
        self.velocity = velocity
        self.max_available_seats = max_available_seats


class DynamicRoutingConfig:
    def __init__(
        self,
        action_space: DiscreteActionSpace,
        action_resolution: int,
        corridor,
        learning_agent,
        penalty: Union[int, float],
        reward: Union[int, float],
        timelimit_multiplier: float,
        use_learning_agent: bool,
    ):
        self.action_resolution = action_resolution
        self.action_space = action_space
        # a bus that doesn't use a learning agent moves as planned without rerouting
        self.use_learning_agent = use_learning_agent
        self.learning_agent = learning_agent
        self.corridor = corridor
        self.penalty = penalty
        self.problem = None  # defer initialization
        self.reward = reward
        self.timelimit_multiplier = timelimit_multiplier


class DynamicCheckpointRoutingConfig:
    def __init__(
        self,
        action_space: DiscreteActionSpace,
        action_resolution: int,
        checkpoints,
        corridor,
        penalty_checkpoints: Union[int, float],
        penalty_goingback: Union[int, float],
        penalty_unreachable: Union[int, float],
        periodic_testing: Optional[int],
        reward: Union[int, float],
        timelimit_multiplier: float,
        use_learning_agent: bool,
    ):
        self.action_resolution = action_resolution
        self.action_space = action_space
        # a bus that doesn't use a learning agent moves as planned without rerouting
        self.use_learning_agent = use_learning_agent
        self.learning_agent = None  # defer initialization
        self.checkpoints = checkpoints
        self.corridor = corridor
        self.area = None  # poly area of the corridor, defer initialization
        self.alignment_cache = None  # defer initialization
        self.alignment_cell_cache = None  # defer initialization
        self.direction = None  # defer initialization
        self.penalty_checkpoints = penalty_checkpoints
        self.penalty_goingback = penalty_goingback
        self.penalty_unreachable = penalty_unreachable
        self.periodic_testing = periodic_testing
        self.problem = None  # defer initialization
        self.reward = reward
        self.timelimit_multiplier = timelimit_multiplier


class DQNConfig:
    # TODO: sort alphabetically or by some grouping logic
    def __init__(
        self,
        episode: int,
        episodes: int,
        alpha: float,
        eps: float,
        eps_decay_strategy: str,
        eps_decay: str,
        eps_max: float,
        eps_min: float,
        buffersize: int,
        replaybuffer: Optional[Union[list, Deque]],
        min_experience: int,
        target_update_threshold: int,
        tau: Optional[float],
        gamma: float,
        weights,
        q_net_layer,
        tensorboard,
        train_frequency: int,
        batchsize: int,
        lr_decay,
        lr_decay_steps,
        double_q,
    ):
        self.alpha = alpha
        self.batchsize = batchsize
        self.episode = episode
        self.episodes = episodes
        self.eps = eps
        self.eps_decay_strategy = eps_decay_strategy
        self.eps_decay = eps_decay
        self.eps_max = eps_max
        self.eps_min = eps_min
        self.replaybuffer_size = buffersize
        self.replaybuffer = replaybuffer
        self.min_experience = min_experience
        self.train_frequency = train_frequency
        self.double_q = double_q
        self.target_update_threshold = target_update_threshold
        self.tau = tau
        self.gamma = gamma
        self.tensorboard = tensorboard
        self.q_net_layer = q_net_layer
        self.optimizer = None
        self.lr_decay = lr_decay
        self.lr_decay_steps = lr_decay_steps
        self.evaluation = False  # on an evaluation run, no training happens and eps = 0
        self.weights = weights
