"""
Configuration module for simulation settings.

This module provides a Configuration class that loads and manages all simulation parameters from a TOML file using Pydantic models.

Each configuration section is represented by a dedicated class, which loads the TOML file, validates its contents,
and exposes each section as a lazily loaded property.

Validation and type checking are handled by Pydantic. To add a new configuration section:

1. Add the section to the TOML config file as a new table (e.g., [new_section]).
2. Create a new Pydantic model for the section in this file, using ConfigBaseModel.
3a. Add a property to the Configuration class that uses _get_section to load and validate the new section.
3b. If the section contains a list or dictionary, use _get_section_list or _get_section_dict respectively.

To add a new parameter to an existing section:
1. Add the parameter to the TOML config file under the appropriate section.
2. Add the parameter to the corresponding Pydantic model, with an appropriate type hint.

All validation, type conversion, and defaults should be handled using Pydantic features (validators, model_config, etc.).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from simulation.helper.configuration.enums import (
    AutonomyType,
    DailyResolution,
    ModeChoiceStrategy,
    PropulsionType,
    SpatialResolution,
    TemporalResolution,
    VehicleType,
)
from simulation.helper.time import SimulationVelocityConverter
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.operator.operations_management.operations import OperationsInterface
from simulation.operator.operator import Operator
from simulation.world.markets.auction import Auction
from simulation.world.markets.shared_charging_auction import SharedChargingAuction

if TYPE_CHECKING:
    # Careful moving stuff here, pydantic needs to check type hints at runtime!
    from types import ModuleType

    from pyparsing import Any


try:
    import tomllib  # future proofing for python 3.11+
except ModuleNotFoundError:
    import pip._vendor.tomli as tomllib

T = TypeVar("T", bound=BaseModel)


class ConfigBaseModel(BaseModel):
    """Base model for all configuration models."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class SettingsConfig(ConfigBaseModel):
    """Global settings for the simulation environment."""

    LOG_LEVEL: str = Field(pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    FILE_LOG_LEVEL: str = Field(pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_TIMESTAMPS: bool
    LOG_CLASS_OVERRIDES: dict[str, str] | None = None
    PERSIST_RESULTS: bool  # TODO: Remove or properly implement

    @field_validator("LOG_CLASS_OVERRIDES", mode="after")
    @classmethod
    def validate_log_overrides(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        """Validate log class overrides."""
        if v is None:
            return v
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        for class_name, level in v.items():
            if level not in valid_levels:
                raise ValueError(
                    f"Invalid log level '{level}' for class '{class_name}'"
                )
        return v


class ExperimentManagementConfig(ConfigBaseModel):
    """Configuration for experiment management."""

    START_TIME: int = Field(ge=0)
    END_TIME: int = Field(gt=0)


class RandomManagerConfig(ConfigBaseModel):
    """Configuration for random number generation."""

    SEED: int = Field(ge=0)
    COMPONENT_SEEDS: dict[str, int]

    @field_validator("COMPONENT_SEEDS", mode="after")
    @classmethod
    def validate_component_seeds(cls, v: dict[str, int]) -> dict[str, int]:
        """Validate that all component seeds are within the valid range."""
        for component, seed in v.items():
            if not (0 <= seed <= 2**32 - 1):
                raise ValueError(
                    f"Seed for component '{component}' must be between 0 and {2**32 - 1}"
                )
        return v


class WorldConfig(ConfigBaseModel):
    """Configuration for the simulation world."""

    SPATIAL_RESOLUTION: SpatialResolution
    DAILY_RESOLUTION: DailyResolution
    TEMPORAL_RESOLUTION: TemporalResolution
    CITY: str


class PathConfig(ConfigBaseModel):
    """Configuration for file paths used in the simulation."""

    PATH_ENV_BOUNDING_BOX: Path
    PATH_ENV_HEX_LAYER_RES_7: Path
    PATH_ENV_HEX_LAYER_RES_8: Path
    PATH_ENV_HEX_LAYER_RES_9: Path
    PATH_TRANSIT_TIMETABLE: Path
    PATH_TRANSIT_SHAPES: Path
    PATH_VEHICLE_SUPPLY: Path
    PATH_TO_MODE_CHOICE_MODEL: Path
    OUTPUT_FOLDER: Path
    TRANSACTION_FILE: Path
    FLEET_STATE_FILE: Path
    PATH_TRIP_DEMAND: Path
    PATH_DEMAND_MODIFIERS: list[Path] | None = None

    @field_validator("*", mode="after")
    @classmethod
    def normalize_paths(cls, v: str | Path | list[Path]) -> Path | list[Path]:
        """Normalize and expand paths."""
        if isinstance(v, list):
            return [Path(os.path.normpath(str(item.expanduser()))) for item in v]
        if isinstance(v, Path):
            return Path(os.path.normpath(str(v.expanduser())))
        if isinstance(v, str):
            return Path(os.path.normpath(os.path.expanduser(v)))


class PopulationConfig(ConfigBaseModel):
    """Configuration for population demographics and probabilities."""

    POPULATION_PROBABILITIES: list[float] = Field(min_length=1)
    RIDE_HAILING_POPULATION_PROBABILITIES: list[float] | None = None
    SHARED_VEHICLE_POPULATION_PROBABILITIES: list[float] | None = None
    TRANSIT_POPULATION_PROBABILITIES: list[float] | None = None

    @field_validator(
        "POPULATION_PROBABILITIES",
        # "RIDE_HAILING_POPULATION_PROBABILITIES",
        # "SHARED_VEHICLE_POPULATION_PROBABILITIES",
        # "TRANSIT_POPULATION_PROBABILITIES",
        mode="after",
    )
    @classmethod
    def validate_probabilities(cls, v: list[float] | None) -> list[float] | None:
        """Validate that probabilities are between 0.0 and 1.0 and sum to 1.0."""
        if v is None:
            return v
        if not all(0.0 <= prob <= 1.0 for prob in v):
            raise ValueError("All probabilities must be between 0.0 and 1.0")
        if abs(sum(v) - 1.0) > 1e-6:
            raise ValueError("Probabilities must sum to 1.0")
        return v


class UserConfig(ConfigBaseModel):
    """Configuration for user behavior and preferences."""

    TRANSIT_MAX_WAIT: int = Field(
        gt=0, description="Maximum wait time for transit in minutes"
    )
    SPATIAL_STRATEGY: str
    WALKING_SPEED: float = Field(gt=0)

    @field_validator("WALKING_SPEED", mode="after")
    @classmethod
    def convert_walking_speed(cls, v: float) -> float:
        """Convert walking speed from km/h to m/s."""
        return SimulationVelocityConverter().convert_kmh(v)


class VehicleConfig(ConfigBaseModel):
    """Configuration for vehicle properties and behavior."""

    VELOCITY: float = Field(gt=0)
    MAX_AVAILABLE_SEATS: int
    VEHICLE_TYPE: VehicleType
    AUTONOMY_TYPE: AutonomyType = AutonomyType.HUMAN_DRIVEN
    PROPULSION_TYPE: PropulsionType = PropulsionType.BATTERY_ELECTRIC
    WALKING_DISTANCE: int | None = Field(default=None, ge=0, le=10000)
    CONVENIENCE: int = Field(default=1, ge=1)
    MAX_STATE_OF_CHARGE: float | None = Field(default=None, gt=0)
    ENERGY_CONSUMPTION: float | None = Field(default=None, ge=0)
    EV_RELATIVE_ENERGY_CONSUMPTION: float | None = Field(default=None, gt=0)
    INITIAL_SOC: float | None = Field(default=None, gt=0)
    EMERGENCY_SOC_BUFFER: float | None = Field(default=None, gt=0)
    PRICE_PER_MIN: float | None = Field(default=None, gt=0)
    PRICE_PER_TRIP: float = Field(default=0, ge=0)
    DAILY_TOTAL_COST: float | None = Field(default=None, gt=0)
    COST_PER_KM: float | None = Field(default=None, gt=0)
    PRICE_PER_KM: float | None = Field(default=None, gt=0)
    CHARGING_COST_PER_KWH: float | None = Field(default=None, gt=0)
    KG_CO2_PER_KM: float | None = Field(default=None, gt=0)

    @field_validator("VELOCITY", mode="after")
    @classmethod
    def convert_velocity(cls, v: float) -> float:
        """Convert vehicle velocity from km/h to m/s."""
        return SimulationVelocityConverter().convert_kmh(v)

    # TODO: Add more validators for other vehicles etc. This is just an example of what we could be doing. Or don't :)
    @model_validator(mode="after")
    def validate_electric_vehicle_fields(self) -> VehicleConfig:
        """Validate fields specific to electric vehicles."""
        if self.PROPULSION_TYPE == PropulsionType.BATTERY_ELECTRIC:
            if self.MAX_STATE_OF_CHARGE is None:
                raise ValueError(
                    "MAX_STATE_OF_CHARGE is required for electric vehicles"
                )
            if self.ENERGY_CONSUMPTION is None:
                raise ValueError("ENERGY_CONSUMPTION is required for electric vehicles")
        return self


class ModeChoiceModelConfig(ConfigBaseModel):
    """Configuration for mode choice model parameters."""

    SUBSTITUTION_BOUNDARY: float
    AV_TRUST: list[float]
    MODE_CHOICE_STRATEGY: ModeChoiceStrategy
    MOD_COEFFICIENTS: list[list[float]]
    MOD_COEFFICIENTS_CI_LOWER: list[list[float]]
    MOD_COEFFICIENTS_CI_UPPER: list[list[float]]
    MOD_P_VALUES: list[list[float]]
    MOD_COEFFICIENT_INTERVAL_ADJUSTER: float


class ChargingInfrastructureConfig(BaseModel):
    """Configuration for charging infrastructure parameters."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=False, arbitrary_types_allowed=True
    )

    NUMBER_OF_CHARGING_STATIONS: int
    LOCATIONS: list[str]
    CHARGING_STATION_POWER: list[float]
    CHARGING_STATION_CAPACITY: list[int]
    CHARGING_STATION_QUEUE_SIZE: list[int]

    # fallback if there is no auction
    COORDINATION_INTERVAL: int | None = Field(gt=0, default=None)
    COORDINATION_TIMESLOT_DURATION: int | None = Field(gt=0, default=None)
    COORDINATION_LOOKAHEAD: int | None = Field(ge=0, default=None)

    # market
    AUCTION_CONFIG: AuctionConfig | None = Field(default=None)

    # Instance is put here after creation, so the operator gets a reference
    instance: ChargingInfrastructure | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def clamp_and_expand(self) -> ChargingInfrastructureConfig:
        """
        Clamp and expand charging infrastructure lists to match the number of stations.

        This method ensures that the LOCATIONS, CHARGING_STATION_POWER, CHARGING_STATION_CAPACITY,
        and CHARGING_STATION_QUEUE_SIZE lists are all of the same length as NUMBER_OF_CHARGING_STATIONS.
        If any of these lists have only a single element, it will be expanded to match the number of stations by
        repeating the single element.

        #TODO: This system is not very intuitive, consider changing it.

        Returns
        -------
        ChargingInfrastructureConfig
            The same instance with updated fields.
        """
        n = self.NUMBER_OF_CHARGING_STATIONS

        self.LOCATIONS = self.LOCATIONS[:n]

        if len(self.CHARGING_STATION_POWER) == 1:
            self.CHARGING_STATION_POWER = self.CHARGING_STATION_POWER * n
        if len(self.CHARGING_STATION_CAPACITY) == 1:
            self.CHARGING_STATION_CAPACITY = self.CHARGING_STATION_CAPACITY * n
        if len(self.CHARGING_STATION_QUEUE_SIZE) == 1:
            self.CHARGING_STATION_QUEUE_SIZE = self.CHARGING_STATION_QUEUE_SIZE * n

        return self


class OperationsConfig(ConfigBaseModel):
    """Configuration for operations parameters."""

    OPERATIONS_START: int | None = Field(ge=0, default=None)
    OPERATIONS_DURATION: int | None = Field(gt=0, default=None)
    TIME_BETWEEN_OPERATIONS: int | None = Field(gt=0, default=None)

    RECHARGE_THRESHOLD: list[float] | float | None = Field(
        default=None
    )  # TODO: unify this between sv and rh
    VEHICLE_RELOCATION_VELOCITY: float | None = Field(gt=0, default=None)

    ALLOW_QUEUE: bool | None = Field(default=False)
    NUMBER_OF_SERVICE_WORKERS: int | None = Field(default=None, gt=0)

    PLANNING_LOOKAHEAD: int | None = Field(default=None, gt=0)

    BID_DEFAULT: float | None = Field(gt=0, default=None)
    BID_DECAY: float | None = Field(gt=0, default=None)
    RANDOM_OVERBIDDING: bool | None = Field(default=None)
    OVERBID_PROB: float | None = Field(gt=0, default=None)
    LOW_SOC_PENALTY: int | None = Field(gt=0, default=None)

    @field_validator("VEHICLE_RELOCATION_VELOCITY", mode="after")
    @classmethod
    def convert_velocity(cls, v: float) -> float:
        """Convert vehicle relocation velocity from km/h to m/s."""
        return SimulationVelocityConverter().convert_kmh(v)


class OperatorConfig(ConfigBaseModel):
    """Configuration for operator parameters."""

    # TODO: https://github.com/IS3UniCologne/urban-mobility-simulation/issues/211 should go here

    # AVAILABLE_MODES: list[AutonomyType]
    # AVAILABLE_MODES_SUPPLY: list[int]
    OPERATOR_TYPE: type[Operator]

    # TODO: We should move operations type into the operations config.
    OPERATIONS_TYPE: type[OperationsInterface]
    OPERATIONS_CONFIG: OperationsConfig

    CHARGING_INFRASTRUCTURE: ChargingInfrastructureConfig | None = Field(default=None)

    # TODO: Shared vehicle stuff, this should be changed once we move to the same charging infrastructure as ridehailing
    CHARGING_STATION_POWER: int | None = Field(default=None)
    NUMBER_OF_BASE_REGIONS: int | None = Field(default=None)
    BASE_CAPACITY: int | None = Field(default=None)
    BASE_REGIONS: list[str] | None = Field(default=None)

    N_VEHICLES: dict[VehicleType, int] | None = Field(default=None)

    # Public transit stuff
    MAX_BUSSES: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def clamp_base_regions(self) -> OperatorConfig:
        """
        Clamp base regions list to match the number of base regions.

        TODO: Same as above, not super intuitive.

        Returns
        -------
        OperatorConfig
            A new instance with updated BASE_REGIONS.
        """
        if self.BASE_REGIONS is None or self.NUMBER_OF_BASE_REGIONS is None:
            return self
        return self.model_copy(
            update={"BASE_REGIONS": self.BASE_REGIONS[: self.NUMBER_OF_BASE_REGIONS]}
        )


class RideHailingGlobalConfig(ConfigBaseModel):
    """Global configuration for ride-hailing parameters."""

    DRIVER_PAYMENT_SHARE: float = Field(gt=0)
    AV_PRICE_REDUCTION: float = Field(gt=0)
    MAX_PICKUP_DISTANCE: int = Field(gt=0)
    PRICE_ENTERING: float = Field(ge=0)
    PRICE_PER_MINUTE: float = Field(ge=0)
    PRICE_PER_KM: float = Field(ge=0)
    MINIMUM_PRICE: float = Field(ge=0)
    ALLOCATION: float = Field(ge=0)
    DISCOUNT_RATE: float = Field(ge=0)
    N_RIDE_HAILING_CARS: int = Field(ge=0)
    N_AUTONOMOUS_CARS: int = Field(ge=0)
    EV_PENETRATION: float = Field(gt=0)
    AV_PENETRATION: float = Field(gt=0)
    RH_AVAILABILITY: list[float]
    DRIVER_AVAILABILITY_VECTOR: list[int] | None = None

    @model_validator(mode="after")
    def apply_discount_and_availability(self) -> RideHailingGlobalConfig:
        """
        Apply discount to price fields and compute driver availability vector.

        Returns
        -------
        RideHailingGlobalConfig
            A new instance with updated price fields and driver availability vector.
        """
        # TODO: Is this functionality really necessary ?
        discount = 1.0 - self.DISCOUNT_RATE
        return self.model_copy(
            update={
                "PRICE_ENTERING": self.PRICE_ENTERING * discount,
                "PRICE_PER_MINUTE": self.PRICE_PER_MINUTE * discount,
                "PRICE_PER_KM": self.PRICE_PER_KM * discount,
                "MINIMUM_PRICE": self.MINIMUM_PRICE * discount,
                "DRIVER_AVAILABILITY_VECTOR": [
                    round(
                        float(x)
                        * self.N_RIDE_HAILING_CARS
                        * (1.0 - self.AV_PENETRATION)
                    )
                    for x in self.RH_AVAILABILITY
                ],
            }
        )


class AuctionConfig(ConfigBaseModel):
    """Configuration for auction parameters."""

    AUCTION_TYPE: type[Auction]

    AUCTION_START: int = Field(ge=0)
    AUCTION_END: int = Field(gt=0)


class SharedChargingAuctionConfig(AuctionConfig):
    """Configuration for shared charging auction parameters."""

    AUCTION_TYPE: type[SharedChargingAuction] = SharedChargingAuction

    AUCTION_INTERVAL: int = Field(gt=0)
    TIMESLOT_DURATION: int = Field(gt=0)
    AUCTION_LOOKAHEAD: int = Field(ge=0)


class DynamicRoutingConfig(ConfigBaseModel):
    """Configuration for dynamic routing parameters."""

    ACTION_SPACE: list[str]
    ACTION_SPACE_RESOLUTION: int
    CORRIDOR_PATH: str
    PENALTY: float
    REWARD: float
    TIMELIMIT: float


class DynamicCheckpointRoutingConfig(ConfigBaseModel):
    """Configuration for dynamic checkpoint routing parameters."""

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


class DQNConfig(ConfigBaseModel):
    """Configuration for DQN parameters."""

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


def _patch_path_city_fields(
    path_data: dict[str, str | list[str]], city: str
) -> dict[str, str | list[str]]:
    """Replace {city} in all string fields of path_data with the given city name."""
    patched = path_data.copy()
    for k, v in patched.items():
        if isinstance(v, str) and "{city}" in v:
            patched[k] = v.format(city=city)
    if patched.get("PATH_DEMAND_MODIFIERS"):
        patched["PATH_DEMAND_MODIFIERS"] = [
            s.format(city=city) for s in patched["PATH_DEMAND_MODIFIERS"]
        ]
    return patched


class Configuration:
    """
    Configuration class for simulation parameters.

    Lazily loads and validates each configuration section only when accessed.
    Preserves type checking and IDE auto-completion for each section property.
    """

    def __init__(self, experiment_dir: str | Path) -> None:
        base = Path(experiment_dir)
        if not base.is_dir():
            raise NotADirectoryError(f"Expected a directory: {base}")

        config_file = base / "config.toml"
        if not config_file.exists():
            raise FileNotFoundError(f'Could not find "config.toml" in {base}')

        with open(config_file, "rb") as f:
            data = tomllib.load(f)

        self._data = {k.lower(): v for k, v in data.items()}
        self._cache: dict[str, object] = {}

        # Eagerly load world and path so we can patch path fields
        world_config = WorldConfig.model_validate(self._data["world"])
        self._cache["world"] = world_config
        city = world_config.CITY
        patched_path = _patch_path_city_fields(self._data["path"], city)
        self._cache["path"] = PathConfig.model_validate(patched_path)

        # Load components that are configured as Python modules
        self._load_config_from_py(base)

    def _get_section(self, section: str, model: type[T]) -> T:
        if section in self._cache:
            return cast("T", self._cache[section])
        if section not in self._data:
            raise AttributeError(f"Config section '{section}' not found")
        try:
            validated_model = model.model_validate(self._data[section])
            self._cache[section] = validated_model
            return cast("T", validated_model)
        except ValidationError as e:
            raise ValueError(
                f"Config validation error in section '{section}': {e}"
            ) from e  # Preserve the exception chain
        except Exception as e:
            raise ValueError(
                f"Unexpected error validating section '{section}': {e}"
            ) from e

    def _get_section_list(self, section: str, model: type[T]) -> list[T]:
        """Get a section that contains a list of items."""
        if section in self._cache:
            return self._cache[section]

        items = self._data.get(section)
        if items is None:
            result = []
        else:
            result = [model.model_validate(item) for item in items]

        self._cache[section] = result
        return result

    def _get_section_dict(
        self, section: str, model: type[T], allow_none: bool = False
    ) -> dict[str, T] | None:
        """Get a section that contains a dictionary of items."""
        if section in self._cache:
            return self._cache[section]

        items = self._data.get(section)
        if items is None:
            result = None if allow_none else {}
        else:
            result = {k: model.model_validate(v) for k, v in items.items()}

        self._cache[section] = result
        return result

    @property
    def settings(self) -> SettingsConfig:
        """
        Get the settings configuration section.

        Returns
        -------
        SettingsConfig
            The settings configuration section.
        """
        return self._get_section("settings", SettingsConfig)

    @property
    def experiment_management(self) -> ExperimentManagementConfig:
        """
        Get the experiment management configuration section.

        Returns
        -------
        ExperimentManagementConfig
            The experiment management configuration section.
        """
        return self._get_section("experiment_management", ExperimentManagementConfig)

    @property
    def random_manager(self) -> RandomManagerConfig:
        """
        Get the random manager configuration section.

        Returns
        -------
        RandomManagerConfig
            The random manager configuration section.
        """
        return self._get_section("random_manager", RandomManagerConfig)

    @property
    def world(self) -> WorldConfig:
        """
        Get the world configuration section.

        Returns
        -------
        WorldConfig
            The world configuration section.
        """
        return self._get_section("world", WorldConfig)

    @property
    def path(self) -> PathConfig:
        """
        Get the path configuration section.

        Returns
        -------
        PathConfig
            The path configuration section.
        """
        return self._get_section("path", PathConfig)

    @property
    def population(self) -> PopulationConfig:
        """
        Get the population configuration section.

        Returns
        -------
        PopulationConfig
            The population configuration section.
        """
        return self._get_section("population", PopulationConfig)

    @property
    def user(self) -> UserConfig:
        """
        Get the user configuration section.

        Returns
        -------
        UserConfig
            The user configuration section.
        """
        return self._get_section("user", UserConfig)

    @property
    def mode_choice_model(self) -> ModeChoiceModelConfig:
        """
        Get the mode choice model configuration section.

        Returns
        -------
        ModeChoiceModelConfig
            The mode choice model configuration section.
        """
        return self._get_section("mode_choice_model", ModeChoiceModelConfig)

    @property
    def charging_infrastructures(self) -> list[ChargingInfrastructureConfig]:
        """
        Get the charging infrastructure configuration section.

        Returns
        -------
        ChargingInfrastructureConfig
            The charging infrastructure configuration section.
        """
        return self._get_section_list(
            "charging_infrastructure", ChargingInfrastructureConfig
        )

    @property
    def operators(self) -> list[OperatorConfig]:
        """
        Get the operators configuration section.

        Returns
        -------
        list[OperatorConfig]
            The operators configuration section.
        """
        return self._get_section_list("operator", OperatorConfig)

    @property
    def ride_hailing_vehicles(self) -> dict[str, VehicleConfig]:
        """
        Get the ride hailing vehicles configuration section.

        Returns
        -------
        dict[str, VehicleConfig]
            The ride hailing vehicles configuration section.
        """
        return self._get_section_dict("ride_hailing_vehicles", VehicleConfig)

    @property
    def shared_vehicles(self) -> dict[VehicleType, VehicleConfig]:
        """
        Get the shared vehicles configuration section.

        Returns
        -------
        dict[VehicleType, VehicleConfig]
            The shared vehicles configuration section.
        """
        section_name = "shared_vehicles"
        if section_name in self._cache:
            return cast("dict[VehicleType, VehicleConfig]", self._cache[section_name])

        items = self._data.get(section_name)
        if items is None:
            result = {}
        else:
            result = {
                VehicleType(k): VehicleConfig.model_validate(v)
                for k, v in items.items()
            }

        self._cache[section_name] = result
        return result

    @property
    def transit_vehicles(self) -> dict[str, VehicleConfig] | None:
        """Get the transit vehicles configuration section.

        Returns
        -------
        dict[str, VehicleConfig] | None
            The transit vehicles configuration section, or None if not defined.
        """
        return self._get_section_dict(
            "transit_vehicles", VehicleConfig, allow_none=True
        )

    @property
    def ride_hailing_global(self) -> RideHailingGlobalConfig:
        """Get the global ride hailing configuration section.

        Returns
        -------
        RideHailingGlobalConfig
            The global ride hailing configuration section.
        """
        return self._get_section("ride_hailing_global", RideHailingGlobalConfig)

    @property
    def auction(self) -> AuctionConfig:
        """Get the auction configuration section.

        Returns
        -------
        AuctionConfig
            The auction configuration section.
        """
        return self._get_section("auction", AuctionConfig)

    @property
    def shared_charging_auction(self) -> SharedChargingAuctionConfig | None:
        """Get the shared charging auction configuration section.

        Returns
        -------
        SharedChargingAuctionConfig | None
            The shared charging auction configuration section, or None if not defined.
        """
        section = "shared_charging_auction"
        if section in self._cache:
            return cast("SharedChargingAuctionConfig | None", self._cache[section])
        if section not in self._data:
            self._cache[section] = None
            return None
        return self._get_section(section, SharedChargingAuctionConfig)

    @property
    def dynamic_routing(self) -> DynamicRoutingConfig:
        """Get the dynamic routing configuration section.

        Returns
        -------
        DynamicRoutingConfig
            The dynamic routing configuration section.
        """
        return self._get_section("dynamic_routing", DynamicRoutingConfig)

    @property
    def dynamic_checkpoint_routing(self) -> DynamicCheckpointRoutingConfig:
        """Get the dynamic checkpoint routing configuration section.

        Returns
        -------
        DynamicCheckpointRoutingConfig
            The dynamic checkpoint routing configuration section.
        """
        return self._get_section(
            "dynamic_checkpoint_routing", DynamicCheckpointRoutingConfig
        )

    @property
    def dqn(self) -> DQNConfig:
        """Get the DQN configuration section.

        Returns
        -------
        DQNConfig
            The DQN configuration section.
        """
        return self._get_section("dqn", DQNConfig)

    def _load_config_from_py(self, base_path: Path) -> None:
        op_file = base_path / "operators.py"
        if not op_file.exists():
            raise FileNotFoundError(f'Could not find "operators.py" in {base_path}')

        module = self._import_module_file(op_file)

        section_buckets: dict[str, list[Any]] = {
            "operator": [],
            "charging_infrastructure": [],
        }

        model_to_section: dict[type[BaseModel], str] = {
            OperatorConfig: "operator",
            ChargingInfrastructureConfig: "charging_infrastructure",
        }
        model_classes = tuple(model_to_section.keys())

        def collect(obj: object) -> None:
            if isinstance(obj, model_classes):
                for cls in model_to_section:
                    if isinstance(obj, cls):
                        section_buckets[model_to_section[cls]].append(obj)
                        return
            if isinstance(obj, list | tuple):
                for elem in obj:
                    collect(elem)
                return
            # nothing matches, ignore

        for name, value in vars(module).items():
            if name.startswith("_"):
                continue
            collect(value)

        for section_name, items in section_buckets.items():
            self._cache[section_name] = items

    def _import_module_file(self, file_path: Path) -> ModuleType:
        """Import a module from a filesystem .py file path."""
        spec = importlib.util.spec_from_file_location("ums_py_config", file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for {file_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
