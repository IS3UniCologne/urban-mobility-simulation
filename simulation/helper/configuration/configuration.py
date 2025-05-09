import ast
import sys
from dataclasses import dataclass, fields
from functools import wraps
from typing import Any, Optional, TypeVar

import numpy as np

from simulation.helper.configuration.enums import (
    DailyResolution,
    ModeChoiceStrategy,
    PopulationType,
    SpatialResolution,
    TemporalBucket,
    VehicleMode,
)
from simulation.helper.singleton import Singleton
from simulation.helper.time import SimulationVelocityConverter

try:
    import tomllib  # future proofing for python 3.11+
except ModuleNotFoundError:
    import pip._vendor.tomli as tomllib

from beartype import BeartypeConf, beartype
from beartype.door import die_if_unbearable

# remove color from beartype exceptions to avoid unreadable debug output,
# might want to move this to the templates to apply it to all beartype exceptions
BeartypeConf.is_color = False  # type: ignore


"""
The configuration class holds all the configuration parameters for the simulation and is loaded from the config toml file.
The class is a singleton, meaning that there is only one instance of the class that is shared across the entire simulation.
The config classes are lazy loaded, meaning that the configuration objects are only created when they are accessed for the first time.
The input from the config file is validated using beartype.

To add a new configuration parameter to an existing configuration class, follow these steps:
1. Add the parameter to the config.toml file in the correct table.
2. Add the parameter to the Configuration class. Make sure to include a type hint.
3. If the parameter is optional, add the None type hint and set the default value to None. (e.g.  OPTIONAL_LIST: None | list[str] = None)
    All optional parameters have to be at the end of the dataclass. This is a limitation of dataclasses.
4. Types that are not supported by toml (e.g. Enums,Tuples) should be converted to their respective types in the __post_init__ method. Make sure to use
    the @beartype_after_post_init decorator if you do this.

To add a new configuration class, follow these steps:
1. Create a new table int the config file, e.g. [NEW_TABLE]. 
2. Create a new dataclass in this file, e.g. class NewTableConfig. Please keep the order of dataclasses the same as in the config file.
3. Add the dataclass to the Configuration class as a property.
Example: 
@property
    def new_table(self) -> NewTableConfig:
        return self._get_lazy_object("new_table", NewTableConfig)
        
For an exmaple of how to implement Lists, look at the Operator configs.
For an example of how to implement nested dictionaries, look at the Vehicle configs.
"""

# Generic type variable for type hinting
T = TypeVar("T", bound=type)


def beartype_after_post_init(cls: T) -> T:
    """Decorator to that delays the beartype check until after the __post_init__ method is called."""
    original_post_init = getattr(cls, "__post_init__", None)

    if original_post_init:

        @wraps(original_post_init)
        def wrapped_post_init(self: Any) -> None:  # noqa: ANN401
            original_post_init(self)
            for field in fields(self):
                value = getattr(self, field.name)
                die_if_unbearable(
                    obj=value,
                    hint=field.type,
                    exception_prefix=f"Field '{field.name}' in {self.__class__.__name__} is not of type {field.type}: ",
                )

        setattr(cls, "__post_init__", wrapped_post_init)
    else:
        # If no original post_init, create a function without @wraps
        def default_post_init(self: Any) -> None:  # noqa: ANN401
            for field in fields(self):
                value = getattr(self, field.name)
                die_if_unbearable(
                    obj=value,
                    hint=field.type,
                    exception_prefix=f"Field '{field.name}' in {self.__class__.__name__} is not of type {field.type}: ",
                )

        setattr(cls, "__post_init__", default_post_init)
    return cls


@beartype
@dataclass(slots=True, frozen=True)
class SettingsConfig:
    LOG_LEVEL: str
    FILE_LOG_LEVEL: str

    PERSIST_RESULTS: bool
    TRACK_AGENT: bool


@beartype
@dataclass(slots=True, frozen=True)
class ExperimentManagementConfig:
    START_TIME: int
    END_TIME: int


@beartype
@dataclass(slots=True, frozen=True)
class RandomManagerConfig:
    SEED: int
    COMPONENT_SEEDS: dict[str, int]


@beartype_after_post_init
@dataclass(slots=True, frozen=True)
class WorldConfig:
    SPATIAL_RESOLUTION: SpatialResolution
    TEMPORAL_RESOLUTION: TemporalBucket
    DAILY_RESOLUTION: DailyResolution
    CITY: str

    def __post_init__(self) -> None:
        # convert ints to enums
        object.__setattr__(
            self, "SPATIAL_RESOLUTION", SpatialResolution(self.SPATIAL_RESOLUTION)
        )
        object.__setattr__(
            self, "TEMPORAL_RESOLUTION", TemporalBucket(self.TEMPORAL_RESOLUTION)
        )
        object.__setattr__(
            self, "DAILY_RESOLUTION", DailyResolution(self.DAILY_RESOLUTION)
        )

    @property
    def SPATIAL_RESOLUTION_VALUE(self) -> int:
        return self.SPATIAL_RESOLUTION.value

    @property
    def SPATIAL_RESOLUTION_COLUMN(self) -> str:
        """Returns the column name for the spatial resolution. E.g. 'hex_id_7'

        Returns:
            str: Column name, e.g. 'hex_id_7'
        """
        return f"hex_id_{self.SPATIAL_RESOLUTION_VALUE}"


@beartype
@dataclass(slots=True, frozen=True)
class PathConfig:
    PATH_ENV_BOUNDING_BOX: str
    PATH_ENV_HEX_LAYER_RES_7: str
    PATH_ENV_HEX_LAYER_RES_8: str
    PATH_ENV_HEX_LAYER_RES_9: str

    PATH_TRANSIT_TIMETABLE: str
    PATH_TRANSIT_SHAPES: str

    PATH_VEHICLE_SUPPLY: str

    PATH_TO_MODE_CHOICE_MODEL: str

    OUTPUT_FOLDER: str
    TRANSACTION_FILE: str
    FLEET_STATE_FILE: str

    PATH_TRIP_DEMAND: str
    PATH_DEMAND_MODIFIERS: Optional[list[str]] = None

    def __post_init__(self) -> None:
        city = Configuration().world.CITY
        for field_obj in fields(self):
            field_name = field_obj.name
            value = getattr(self, field_name)
            if isinstance(value, str) and "{city}" in value:
                # Use object.__setattr__ to bypass dataclass immutability with frozen
                object.__setattr__(self, field_name, value.format(city=city))

        # Format demand modifiers if present
        if self.PATH_DEMAND_MODIFIERS:
            formatted_modifiers = [
                value.format(city=city) for value in self.PATH_DEMAND_MODIFIERS
            ]
            object.__setattr__(self, "PATH_DEMAND_MODIFIERS", formatted_modifiers)


@beartype
@dataclass(slots=True, frozen=True)
class PopulationConfig:
    POPULATION_PROBABILITIES: list[float]
    RIDE_HAILING_POPULATION_PROBABILITIES: list[float]
    SHARED_VEHICLE_POPULATION_PROBABILITIES: list[float]
    TRANSIT_POPULATION_PROBABILITIES: list[float]


@beartype_after_post_init
@dataclass(slots=True, frozen=True)
class UserConfig:
    TRANSIT_MAX_WAIT: int
    SPATIAL_STRATEGY: str
    WALKING_SPEED: float

    def __post_init__(self) -> None:
        # convert km/h to m/s
        object.__setattr__(
            self,
            "WALKING_SPEED",
            SimulationVelocityConverter.convert_kmh(self.WALKING_SPEED),
        )


@beartype_after_post_init
@dataclass(slots=True, frozen=True)
class VehicleConfig:
    VELOCITY: float
    MAX_AVAILABLE_SEATS: int

    WALKING_DISTANCE: Optional[int] = None

    MAX_STATE_OF_CHARGE: Optional[float] = None
    ENERGY_CONSUMPTION: Optional[float] = None
    EV_RELATIVE_ENERGY_CONSUMPTION: Optional[float] = None
    INITIAL_SOC: Optional[float] = None
    EMERGENCY_SOC_BUFFER: Optional[float] = None

    PRICE_PER_MIN: Optional[float] = None
    DAILY_TOTAL_COST: Optional[float] = None
    COST_PER_KM: Optional[float] = None
    PRICE_PER_KM: Optional[float] = None
    CHARGING_COST_PER_KWH: Optional[float] = None
    KG_CO2_PER_KM: Optional[float] = None

    def __post_init__(self) -> None:
        # convert velocity km/h to m/s
        object.__setattr__(
            self, "VELOCITY", SimulationVelocityConverter.convert_kmh(self.VELOCITY)
        )


@beartype_after_post_init
@dataclass(slots=True, frozen=True)
class ModeChoiceModelConfig:
    SUBSTITUTION_BOUNDARY: float
    AV_TRUST: list[float]
    MODE_CHOICE_STRATEGY: ModeChoiceStrategy

    # MoD
    MOD_COEFFICIENTS: list[list[float]]
    MOD_COEFFICIENTS_CI_LOWER: list[list[float]]
    MOD_COEFFICIENTS_CI_UPPER: list[list[float]]
    MOD_P_VALUES: list[list[float]]
    MOD_COEFFICIENT_INTERVAL_ADJUSTER: float

    def __post_init__(self) -> None:
        # convert from str to enum
        object.__setattr__(
            self,
            "MODE_CHOICE_STRATEGY",
            ModeChoiceStrategy[str(self.MODE_CHOICE_STRATEGY)],
        )

    def generate_mode_choice_coefficients(
        self, population_type: PopulationType
    ) -> np.ndarray:
        # TODO: This shouldn't be in here, can't use random manager because of circular import, fix once it's moved
        rng = np.random.default_rng(seed=Configuration().random_manager.SEED)
        mode_choice_coefficients_ci_lower = self.MOD_COEFFICIENTS_CI_LOWER[
            population_type.value
        ]
        mode_choice_coefficients_ci_upper = self.MOD_COEFFICIENTS_CI_UPPER[
            population_type.value
        ]
        # turn into np arrays for computation
        mode_choice_coefficients_ci_lower = np.array(mode_choice_coefficients_ci_lower)
        mode_choice_coefficients_ci_upper = np.array(mode_choice_coefficients_ci_upper)

        interval_adjuster = self.MOD_COEFFICIENT_INTERVAL_ADJUSTER

        adjuster = (
            (mode_choice_coefficients_ci_upper - mode_choice_coefficients_ci_lower)
            / 2
            * interval_adjuster
        )
        mode_choice_coefficients_ci_lower = mode_choice_coefficients_ci_lower + adjuster
        mode_choice_coefficients_ci_upper = mode_choice_coefficients_ci_upper - adjuster
        mode_choice_coefficients = rng.uniform(
            mode_choice_coefficients_ci_lower, mode_choice_coefficients_ci_upper
        )
        return mode_choice_coefficients

    def generate_AV_trust(self, population_type: PopulationType) -> float:
        # TODO: This shouldn't be in here, can't use random manager because of circular import, fix once it's moved
        rng = np.random.default_rng(seed=Configuration().random_manager.SEED)
        trust_value_lower = self.AV_TRUST[population_type.value] - 0.5
        trust_value_upper = self.AV_TRUST[population_type.value] + 0.5
        trust_value = rng.uniform(trust_value_lower, trust_value_upper)
        return trust_value


@beartype
@dataclass(slots=True, frozen=True)
class ChargingInfrastructureConfig:
    NUMBER_OF_CHARGING_STATIONS: int
    LOCATIONS: list[str]
    CHARGING_STATION_POWER: list[float]
    CHARGING_STATION_CAPACITY: list[int]
    CHARGING_STATION_QUEUE_SIZE: list[int]

    def __post_init__(self) -> None:
        # clamplocations to number of charging stations
        object.__setattr__(
            self, "LOCATIONS", self.LOCATIONS[: self.NUMBER_OF_CHARGING_STATIONS]
        )

        # If power, capacity, and queue size are single values, repeat them for all locations
        if len(self.CHARGING_STATION_POWER) == 1:
            object.__setattr__(
                self,
                "CHARGING_STATION_POWER",
                self.CHARGING_STATION_POWER * len(self.LOCATIONS),
            )
        if len(self.CHARGING_STATION_CAPACITY) == 1:
            object.__setattr__(
                self,
                "CHARGING_STATION_CAPACITY",
                self.CHARGING_STATION_CAPACITY * len(self.LOCATIONS),
            )
        if len(self.CHARGING_STATION_QUEUE_SIZE) == 1:
            object.__setattr__(
                self,
                "CHARGING_STATION_QUEUE_SIZE",
                self.CHARGING_STATION_QUEUE_SIZE * len(self.LOCATIONS),
            )

        # make sure all lists have the same length
        if len(self.CHARGING_STATION_POWER) != len(self.LOCATIONS):
            raise ValueError(
                "Charging station power and locations must have the same length or be a single value"
            )
        if len(self.CHARGING_STATION_CAPACITY) != len(self.LOCATIONS):
            raise ValueError(
                "Charging station capacity and locations must have the same length or be a single value"
            )
        if len(self.CHARGING_STATION_QUEUE_SIZE) != len(self.LOCATIONS):
            raise ValueError(
                "Charging station queue size and locations must have the same length or be a single value"
            )


@beartype_after_post_init
@dataclass(slots=True, frozen=True)
class SharedVehicleOperatorConfig:
    RECHARGE_THRESHOLD: float
    CHARGING_STATION_POWER: float
    NUMBER_OF_BASE_REGIONS: int
    NUMBER_OF_SERVICE_WORKERS: int
    BASE_CAPACITY: int
    OPERATIONS_START: int
    OPERATIONS_DURATION: int
    VEHICLE_RELOCATION_VELOCITY: float
    BASE_REGIONS: list[str]

    N_VEHICLES: dict[VehicleMode, int]

    def __post_init__(self) -> None:
        # clamp to number of base regions
        object.__setattr__(
            self, "BASE_REGIONS", self.BASE_REGIONS[: self.NUMBER_OF_BASE_REGIONS]
        )

        # convert km/h to m/s
        object.__setattr__(
            self,
            "VEHICLE_RELOCATION_VELOCITY",
            SimulationVelocityConverter.convert_kmh(self.VEHICLE_RELOCATION_VELOCITY),
        )

        # Convert strings in VEHICLES to enum
        object.__setattr__(
            self,
            "N_VEHICLES",
            {VehicleMode[str(mode)]: count for mode, count in self.N_VEHICLES.items()},
        )

    @property
    def AVAILABLE_VEHICLE_MODES(self) -> list[str]:
        # return list of vehicle modes as strings, probably change this later once we have enums everywhere
        return [mode.name for mode in self.N_VEHICLES.keys()]

    @property
    def AVAILABLE_MODES_SUPPLY(self) -> list[int]:
        return list(self.N_VEHICLES.values())


@beartype_after_post_init
@dataclass(slots=True, frozen=True)
class RideHailingOperatorConfig:
    RECHARGE_THRESHOLD: list[float]
    OPERATIONS_START: int
    OPERATIONS_DURATION: int
    VEHICLE_RELOCATION_VELOCITY: float

    def __post_init__(self) -> None:
        # convert velocity km/h to m/s
        object.__setattr__(
            self,
            "VEHICLE_RELOCATION_VELOCITY",
            SimulationVelocityConverter.convert_kmh(self.VEHICLE_RELOCATION_VELOCITY),
        )


@beartype
@dataclass(slots=True, frozen=True)
class TransitOperatorConfig:
    PLANNING_LOOKAHEAD: int
    MAX_BUSSES: int


@beartype_after_post_init
@dataclass(slots=True, frozen=True)
class RideHailingGlobalConfig:
    DRIVER_PAYMENT_SHARE: float
    AV_PRICE_REDUCTION: float
    MAX_PICKUP_DISTANCE: int

    PRICE_ENTERING: float
    PRICE_PER_MINUTE: float
    PRICE_PER_KM: float
    MINIMUM_PRICE: float

    ALLOCATION: float

    DISCOUNT_RATE: float
    N_RIDE_HAILING_CARS: int
    N_AUTONOMOUS_CARS: int
    AVAILABLE_VEHICLE_MODES: list[str]

    # Supply
    EV_PENETRATION: float
    AV_PENETRATION: float
    RH_AVAILABILITY: list[float]

    BID_DEFAULT: float
    BID_DECAY: float
    RANDOM_OVERBIDDING: bool
    OVERBID_PROB: float

    LOW_SOC_PENALTY: int

    DRIVER_AVAILABILITY_VECTOR: list[int] = None  # type: ignore

    def __post_init__(self) -> None:
        # apply the discount rate to all prices
        object.__setattr__(
            self, "PRICE_ENTERING", self.PRICE_ENTERING * (1 - self.DISCOUNT_RATE)
        )
        object.__setattr__(
            self, "PRICE_PER_MINUTE", self.PRICE_PER_MINUTE * (1 - self.DISCOUNT_RATE)
        )
        object.__setattr__(
            self, "PRICE_PER_KM", self.PRICE_PER_KM * (1 - self.DISCOUNT_RATE)
        )
        object.__setattr__(
            self, "MINIMUM_PRICE", self.MINIMUM_PRICE * (1 - self.DISCOUNT_RATE)
        )
        object.__setattr__(
            self,
            "DRIVER_AVAILABILITY_VECTOR",
            [
                round(float(x) * self.N_RIDE_HAILING_CARS * (1 - self.AV_PENETRATION))
                for x in self.RH_AVAILABILITY
            ],
        )

    @property
    def AVAILABLE_MODES_SUPPLY(self) -> list[int]:
        # TODO: This has to be inferred instead of doing it this way. This is very error prone
        return [self.N_AUTONOMOUS_CARS, self.N_RIDE_HAILING_CARS]


@beartype_after_post_init
@dataclass(slots=True, frozen=True)
class SharedVehicleGlobalConfig:
    VEHICLES: Optional[dict[VehicleMode, int]] = None

    def __post_init__(self) -> None:
        # Calculate vehicles as totals from all operators
        object.__setattr__(
            self,
            "VEHICLES",
            {
                mode: sum(
                    [
                        operator.N_VEHICLES.get(mode, 0)
                        for operator in Configuration().shared_vehicle_operators
                    ]
                )
                for mode in VehicleMode
                if any(
                    mode in operator.N_VEHICLES
                    for operator in Configuration().shared_vehicle_operators
                )
            },
        )

    @property
    def AVAILABLE_VEHICLE_MODES(self) -> list[VehicleMode]:
        if not self.VEHICLES:
            return []
        else:
            return list(self.VEHICLES.keys())


# @beartype
# @dataclass(slots=True, frozen=True)
# class TransitGlobalConfig:
#     @property
#     def AVAILABLE_VEHICLE_MODES(self) -> list[str]:
#         # TODO: Use enum for this
#         available_modes = []
#         if self.N_BUSES_TOTAL > 0:
#             available_modes.append("Bus")
#         return available_modes

#     @property
#     def AVAILABLE_MODES_SUPPLY(self) -> list[int]:
#         return [self.N_BUSES_TOTAL]


@beartype
@dataclass(slots=True, frozen=True)
class AuctionConfig:
    AUCTION_START: int
    AUCTION_END: int


@beartype
@dataclass(slots=True, frozen=True)
class SharedChargingAuctionConfig:
    AUCTION_INTERVAL: int
    TIMESLOT_DURATION: int
    AUCTION_LOOKAHEAD: int


@beartype
@dataclass(slots=True, frozen=True)
class DynamicRoutingConfig:
    ACTION_SPACE: list[str]
    ACTION_SPACE_RESOLUTION: int
    CORRIDOR_PATH: str
    PENALTY: float
    REWARD: float
    TIMELIMIT: float


@beartype
@dataclass(slots=True, frozen=True)
class DynamicCheckpointRoutingConfig:
    ACTION_SPACE: list[str]
    ACTION_SPACE_RESOLUTION: int
    CHECKPOINTS: list[int]
    CORRIDOR_PATH: str
    PENALTY_CHECKPOINTS: float
    PENALTY_UNREACHABLE: float
    PENALTY_GOINGBACK: float
    REWARD: float
    TIMELIMIT: float
    PERIODIC_TESTING: int


@beartype_after_post_init
@dataclass(slots=True, frozen=True)
class DQNConfig:
    LR_DECAY: bool
    LR_DECAY_STEPS: int
    DQN_LAYERS: tuple[int, int]
    EPISODES: int
    ALPHA: float
    EPS: float
    EPS_DECAY_STRATEGY: str
    EPS_DECAY: float
    EPS_MAX: float
    EPS_MIN: float
    BUFFERSIZE: int
    REPLAYBUFFER: str
    MIN_EXPERIENCE: int
    TRAIN_FREQUENCY: int
    USE_DOUBLE_Q: bool
    TARGET_UPDATE_THRESHOLD: int
    BATCHSIZE: int
    GAMMA: float

    def __post_init__(self) -> None:
        # evaluate DQN_LAYERS string to tuple
        if isinstance(self.DQN_LAYERS, str):
            self.DQN_LAYERS = ast.literal_eval(self.DQN_LAYERS)


class Configuration(metaclass=Singleton):
    # There is only one instance of this class.
    def __init__(self) -> None:
        config_file = sys.argv[1]
        with open(config_file, "rb") as f:
            self._config_data = tomllib.load(f)  # type: ignore
        self._lazy_objects = {}  # lazy loaded objects are stored here

    @staticmethod
    def _convert_types(params: dict, config_type: type) -> dict:
        """Converts the types of the parameters in the dictionary to the types specified in the dataclass."""
        for field in fields(config_type):
            # cast int to float where applicable
            if field.type == float and field.name in params:
                if isinstance(params[field.name], int):
                    params[field.name] = float(params[field.name])
        return params

    def _get_lazy_config(
        self, name: str, config_type: type, is_dict: bool = False
    ) -> Any:  # noqa: ANN401
        """
        This method will lazily instantiate and return the config object from the config file.
        If the object has already been instantiated, it will return the cached object.
        Args:
            name (str): Config name, should be lower case equivalent to the toml table name (e.g. "world").
            type (type): Type of the Config object.
            is_dict (bool, optional): Set to true for nested dictionaries (e.g. vehicles). Defaults to False.

        Returns:
            _type_: Cached Config Object.
        """
        if name not in self._lazy_objects:
            params = self._config_data.get(name.upper(), None)
            if params is None:
                self._lazy_objects[name] = None
            elif is_dict:
                self._lazy_objects[name] = {
                    k: config_type(**self._convert_types(v, config_type))
                    for k, v in params.items()
                }
            elif isinstance(params, list):
                self._lazy_objects[name] = [
                    config_type(**self._convert_types(param, config_type))
                    for param in params
                ]
            else:
                self._lazy_objects[name] = config_type(
                    **self._convert_types(params, config_type)
                )
        return self._lazy_objects[name]

    @property
    def settings(self) -> SettingsConfig:
        return self._get_lazy_config("settings", SettingsConfig)

    @property
    def experiment_management(self) -> ExperimentManagementConfig:
        return self._get_lazy_config(
            "experiment_management", ExperimentManagementConfig
        )

    @property
    def random_manager(self) -> RandomManagerConfig:
        return self._get_lazy_config("random_manager", RandomManagerConfig)

    @property
    def world(self) -> WorldConfig:
        return self._get_lazy_config("world", WorldConfig)

    @property
    def path(self) -> PathConfig:
        return self._get_lazy_config("path", PathConfig)

    @property
    def population(self) -> PopulationConfig:
        return self._get_lazy_config("population", PopulationConfig)

    @property
    def user(self) -> UserConfig:
        return self._get_lazy_config("user", UserConfig)

    @property
    def mode_choice_model(self) -> ModeChoiceModelConfig:
        return self._get_lazy_config("mode_choice_model", ModeChoiceModelConfig)

    @property
    def charging_infrastructure(self) -> ChargingInfrastructureConfig:
        return self._get_lazy_config(
            "charging_infrastructure", ChargingInfrastructureConfig
        )

    @property
    def shared_vehicle_operators(self) -> list[SharedVehicleOperatorConfig]:
        return self._get_lazy_config(
            "shared_vehicle_operator", SharedVehicleOperatorConfig
        )

    @property
    def ride_hailing_operators(self) -> list[RideHailingOperatorConfig]:
        return self._get_lazy_config("ride_hailing_operator", RideHailingOperatorConfig)

    @property
    def transit_operators(self) -> list[TransitOperatorConfig]:
        return self._get_lazy_config("transit_operator", TransitOperatorConfig)

    @property
    def ride_hailing_global(self) -> RideHailingGlobalConfig:
        return self._get_lazy_config("ride_hailing_global", RideHailingGlobalConfig)

    @property
    def shared_vehicle_global(self) -> SharedVehicleGlobalConfig:
        return self._get_lazy_config("shared_vehicle_global", SharedVehicleGlobalConfig)

    @property
    def ride_hailing_vehicles(self) -> dict[str, VehicleConfig]:
        return self._get_lazy_config(
            "ride_hailing_vehicles", VehicleConfig, is_dict=True
        )

    @property
    def shared_vehicles(self) -> dict[VehicleMode, VehicleConfig]:
        """Dictionary containing VehicleConfig objects for shared vehicles.

        Returns:
            Optional[dict[str, VehicleConfig]]: _description_
        """
        config = self._get_lazy_config("shared_vehicles", VehicleConfig, is_dict=True)

        return {VehicleMode[key]: value for key, value in config.items()}

    @property
    def transit_vehicles(self) -> Optional[dict[str, VehicleConfig]]:
        """Dictionary containing VehicleConfig objects for shared vehicles.

        Returns:
            Optional[dict[str, VehicleConfig]]: _description_
        """
        return self._get_lazy_config("transit_vehicles", VehicleConfig, is_dict=True)

    @property
    def auction(self) -> AuctionConfig:
        return self._get_lazy_config("auction", AuctionConfig)

    @property
    def shared_charging_auction(self) -> SharedChargingAuctionConfig:
        return self._get_lazy_config(
            "shared_charging_auction", SharedChargingAuctionConfig
        )

    ##### Experiment Specific Configurations #####

    @property
    def dynamic_routing(self) -> DynamicRoutingConfig:
        return self._get_lazy_config("dynamic_routing", DynamicRoutingConfig)

    @property
    def dynamic_checkpoint_routing(self) -> DynamicCheckpointRoutingConfig:
        return self._get_lazy_config(
            "dynamic_checkpoint_routing", DynamicCheckpointRoutingConfig
        )

    @property
    def dqn(self) -> DQNConfig:
        return self._get_lazy_config("dqn", DQNConfig)
