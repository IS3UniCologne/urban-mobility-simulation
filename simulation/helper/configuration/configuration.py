"""
Configuration module for simulation settings.

This module provides a Configuration class that loads and manages all simulation parameters from a TOML file using Pydantic models.

Each configuration section is represented by a dedicated class, which loads the TOML file, validates its contents,
and exposes each section as a lazily loaded property.

Validation and type checking are handled by Pydantic. To add a new configuration section:

1. Add the section to the TOML config file as a new table (e.g., [new_section]).
2. Create a new Pydantic model for the section in this file, using ConfigBaseModel.
3. Add a property to the Configuration class that uses _get_section to load and validate the new section.
   If the section contains a list or dictionary, use _get_section_list or _get_section_dict respectively.

To add a new parameter to an existing section:

1. Add the parameter to the TOML config file under the appropriate section.
2. Add the parameter to the corresponding Pydantic model, with an appropriate type hint.

All validation, type conversion, and defaults should be handled using Pydantic features (validators, model_config, etc.).
"""

# TODO: cleanup, with more and more being config-as-code, some of the sections are obsolete

from __future__ import annotations

import importlib.util
import logging
import os
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)

from simulation.agent.user.choice_model.choice_model_interface import (
    ChoiceModelInterface,
)
from simulation.agent.user.choice_model.min_pickup_time_vehicle_choice_model import (
    MinPickupTimeVehicleChoiceModel,
)
from simulation.agent.user.choice_model.random_nearest_vehicle_choice_model import (
    RandomModeNearestVehicleChoiceModel,
)
from simulation.helper.enums import (
    AutonomyType,
    DailyResolution,
    PropulsionType,
    SpatialResolution,
    TemporalResolution,
    VehicleType,
)
from simulation.helper.time import SimulationVelocityConverter
from simulation.helper.types import RegionId
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.operator.mixed_shared_vehicle_fleet import MixedSharedVehicleFleet
from simulation.operator.operations_management.integrated_shared_mobility_operations import (
    IntegratedSharedMobilityOperations,
)
from simulation.operator.operations_management.operations import Operations
from simulation.operator.operator import Operator
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_operator import RideHailingOperator
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.operator.search_engine import SearchEngine
from simulation.operator.shared_mobility_operator import SharedMobilityOperator
from simulation.operator.shared_vehicle_allocation_engine import (
    SharedVehicleAllocationEngine,
)
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
from simulation.operator.vehicle_allocation_engine import AllocationEngine
from simulation.operator.vehicle_fleet import VehicleFleet
from simulation.world.markets.auction import Auction

if TYPE_CHECKING:
    # Careful moving stuff here, pydantic needs to check type hints at runtime!
    from types import ModuleType


T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

LOG_LEVEL_ENV_VAR = "UMOSIM_LOG_LEVEL"
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


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
        for class_name, level in v.items():
            if level not in VALID_LOG_LEVELS:
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


class PathConfig(ConfigBaseModel):
    """Configuration for file paths used in the simulation."""

    DATASET_DIR: Path
    PROJECT_DIR: Path
    OUTPUT_FOLDER: Path
    TRANSACTION_FILE: Path
    FLEET_STATE_FILE: Path

    @field_validator("DATASET_DIR", "PROJECT_DIR", "OUTPUT_FOLDER", mode="after")
    @classmethod
    def normalize_paths(cls, v: Path) -> Path:
        """Normalize and expand absolute paths."""
        return Path(os.path.normpath(str(v.expanduser())))

    @model_validator(mode="after")
    def validate_required_files(self) -> PathConfig:
        """Validate that required dataset files exist."""
        required = [("demand.parquet", self.demand)]
        for name, path in required:
            if not path.exists():
                raise ValueError(
                    f"Required file '{name}' missing in DATASET_DIR (looked at {path})"
                )
        return self

    @classmethod
    def from_raw(cls, data: dict, project_dir: Path) -> PathConfig:
        """Build a PathConfig from raw TOML data, resolving relative paths against project_dir."""
        resolved = data.copy()
        for key in ("DATASET_DIR", "OUTPUT_FOLDER"):
            if key in resolved:
                p = Path(resolved[key]).expanduser()
                resolved[key] = p if p.is_absolute() else (project_dir / p).resolve()
        resolved["PROJECT_DIR"] = project_dir
        return cls.model_validate(resolved)

    @computed_field
    @property
    def dataset_name(self) -> str:
        """Name of the dataset directory (used as identifier, e.g. for cache keys)."""
        return self.DATASET_DIR.name

    @computed_field
    @property
    def bounding_box(self) -> Path | None:
        """Path to bounding_box.geojson, or None if absent (optional, inferred at runtime)."""
        p = self.DATASET_DIR / "bounding_box.geojson"
        return p if p.exists() else None

    @computed_field
    @property
    def demand(self) -> Path:
        """Path to demand.parquet (required)."""
        return self.DATASET_DIR / "demand.parquet"

    @computed_field
    @property
    def supply(self) -> Path | None:
        """Path to dataset-level supply.parquet, or None if absent."""
        p = self.DATASET_DIR / "supply.parquet"
        return p if p.exists() else None

    @computed_field
    @property
    def cache_dir(self) -> Path:
        """Path to the cache directory for derived artifacts."""
        return self.DATASET_DIR / ".cache"

    @computed_field
    @property
    def demand_modifiers(self) -> list[Path]:
        """Paths to demand-modifier GeoJSONs in PROJECT_DIR/demand_modifiers/.

        Returns an empty list if the directory is absent or contains no .geojson files.
        Sorted lexicographically for deterministic load order.
        """
        d = self.PROJECT_DIR / "demand_modifiers"
        if not d.is_dir():
            return []
        return sorted(d.glob("*.geojson"))

    @computed_field
    @property
    def choice_model(self) -> Path | None:
        """Path to choice_model.pickle in project dir, or None if absent (optional, deprecated?)."""
        p = self.PROJECT_DIR / "choice_model.pickle"
        return p if p.exists() else None

    @computed_field
    @property
    def transit_timetable(self) -> Path | None:
        """Path to transit_timetable.parquet, or None if absent (optional)."""
        p = self.DATASET_DIR / "transit_timetable.parquet"
        return p if p.exists() else None

    @computed_field
    @property
    def transit_shapes(self) -> Path | None:
        """Path to transit_shapes.parquet, or None if absent (optional)."""
        p = self.DATASET_DIR / "transit_shapes.parquet"
        return p if p.exists() else None


class UserConfig(ConfigBaseModel):
    """Configuration for user behavior and preferences."""

    TRANSIT_MAX_WAIT: int = Field(
        gt=0, description="Maximum wait time for transit in minutes"
    )  # TODO: this is directly read in the public transport search engine. Either move it to that config or make it a user parameter
    SPATIAL_STRATEGY: str
    WALKING_SPEED_KMH: float = Field(gt=0)
    MAX_SEARCH_DURATION_MIN: int = Field(gt=0)
    CHOICE_MODEL_CONFIG: ChoiceModelConfig


class ChoiceModelConfig(ConfigBaseModel):
    """Configuration for choice model parameters."""

    CHOICE_MODEL_TYPE: type[ChoiceModelInterface]


class RandomModeNearestVehicleChoiceModelConfig(ChoiceModelConfig):
    """Configuration for Random Mode Nearest Vehicle Choice Model parameters."""

    CHOICE_MODEL_TYPE: type[ChoiceModelInterface] = RandomModeNearestVehicleChoiceModel


class MinPickupTimeVehicleChoiceModelConfig(ChoiceModelConfig):
    """Configuration for Minimum Pickup Time Vehicle Choice Model parameters."""

    CHOICE_MODEL_TYPE: type[ChoiceModelInterface] = MinPickupTimeVehicleChoiceModel


class PopulationSegmentConfig(ConfigBaseModel):
    """Configuration for a population segment.

    A segment represents a subset of the user population with distinct behavioral
    characteristics and choice models.
    """

    PROPORTION: float = Field(
        ge=0.0,
        le=1.0,
        description="Proportion of total population in this segment. Must sum to 1.0 across all segments.",
    )
    USER_CONFIG: UserConfig


class PopulationConfig(ConfigBaseModel):
    """Configuration for heterogeneous population of multiple segments.

    Validates that segment proportions sum to 1.0.
    """

    SEGMENTS: list[PopulationSegmentConfig] = Field(
        min_length=1, description="List of population segments"
    )

    @model_validator(mode="after")
    def validate_proportions(self) -> PopulationConfig:
        """Ensure segment proportions sum to 1.0."""
        total = sum(seg.PROPORTION for seg in self.SEGMENTS)
        if not total == 1.0:
            raise ValueError(
                f"Segment proportions must sum to 1.0, got {total:.4f}. "
                f"Segments: {[seg.PROPORTION for seg in self.SEGMENTS]}"
            )
        return self


class VehicleCostConfig(ConfigBaseModel):
    """Operator cost rates for a vehicle."""

    model_config = ConfigDict(frozen=True)

    PER_KM: float = Field(default=0, ge=0)
    CHARGING_PER_KWH: float = Field(default=0, ge=0)
    DAILY: float = Field(default=0, ge=0)
    DRIVER_PAYMENT_SHARE: float = Field(default=0, ge=0, le=1)


class WorkerCostConfig(ConfigBaseModel):
    """Operator cost rates for a service worker."""

    model_config = ConfigDict(frozen=True)

    HOURLY: float = Field(default=0, ge=0)


class VehicleConfig(ConfigBaseModel):
    """Configuration for vehicle properties and behavior."""

    # TODO: check what can be moved to subclasses

    # Make frozen so we can use VehicleConfig in fleet dict
    model_config = ConfigDict(frozen=True)

    VELOCITY_KMH: float = Field(gt=0)
    MAX_AVAILABLE_SEATS: int
    VEHICLE_TYPE: VehicleType
    AUTONOMY_TYPE: AutonomyType = AutonomyType.HUMAN_DRIVEN
    PROPULSION_TYPE: PropulsionType = PropulsionType.BATTERY_ELECTRIC
    ENERGY_CAPACITY: float = Field(gt=0)  # kWh or Liters
    ENERGY_CONSUMPTION_PER_KM: float = Field(ge=0)  # kWh/km or Liters/km
    INITIAL_CHARGE_RATIO: float | None = Field(default=None, ge=0, le=1)
    ENERGY_RESERVE_RATIO: float | None = Field(
        default=None, ge=0, le=1, description="Reserve energy ratio to maintain"
    )
    WALKING_DISTANCE: int | None = Field(
        default=None, ge=0, le=10000
    )  # TODO: Move this to users
    CONVENIENCE: int = Field(default=1, ge=1)
    PRICE_PER_MIN: float | None = Field(default=None, ge=0)
    PRICE_PER_TRIP: float = Field(default=0, ge=0)
    PRICE_PER_KM: float | None = Field(default=None, ge=0)
    KG_CO2_PER_KM: float | None = Field(default=None, ge=0)
    COST_CONFIG: VehicleCostConfig = Field(default_factory=VehicleCostConfig)


class RideHailingVehicleConfig(VehicleConfig):
    """Configuration for ride-hailing vehicle parameters."""


class SharedVehicleConfig(VehicleConfig):
    """Configuration for shared vehicle parameters."""

    PRICE_PER_TRIP: float = Field(default=0)


class FleetConfig(ConfigBaseModel):
    """Configuration for fleet parameters."""

    FLEET_TYPE: type[VehicleFleet]

    VEHICLES: dict[VehicleConfig, int]  # TODO: update this to use distributions

    ENABLE_EN_ROUTE_INDEX: bool = Field(default=False)

    SUPPLY_DISTRIBUTION_FILE: str | None = Field(default=None)

    def supply_distribution_path(self, project_dir: Path) -> Path | None:
        """Resolve the supply distribution filename against a project directory."""
        if self.SUPPLY_DISTRIBUTION_FILE is None:
            return None
        return project_dir / self.SUPPLY_DISTRIBUTION_FILE


class RideHailingFleetConfig(FleetConfig):
    """Configuration for ride-hailing fleet parameters."""

    RH_AVAILABILITY: list[float]
    ENABLE_EN_ROUTE_INDEX: bool = Field(default=True)

    @field_validator("RH_AVAILABILITY", mode="after")
    @classmethod
    def validate_availability_length(cls, v: list[float]) -> list[float]:
        """Validate that RH_AVAILABILITY has exactly 24 elements (one per hour)."""
        if len(v) != 24:
            raise ValueError(
                f"RH_AVAILABILITY must have exactly 24 elements (one per hour), got {len(v)}"
            )
        return v


class SharedVehicleFleetConfig(FleetConfig):
    """Configuration for shared vehicle fleet parameters."""

    FLEET_TYPE: type[VehicleFleet] = MixedSharedVehicleFleet


class ChargingInfrastructureConfig(BaseModel):
    """Configuration for charging infrastructure parameters."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=False, arbitrary_types_allowed=True
    )

    NUMBER_OF_CHARGING_STATIONS: int
    LOCATIONS: list[RegionId]
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

    OPERATIONS_TYPE: type[Operations]

    OPERATIONS_START: int | None = Field(ge=0, default=None)
    OPERATIONS_DURATION: int | None = Field(gt=0, default=None)
    TIME_BETWEEN_OPERATIONS: int | None = Field(gt=0, default=None)

    RECHARGE_THRESHOLD: list[float] | float | None = Field(
        default=None
    )  # TODO: unify this between sv and rh
    VEHICLE_RELOCATION_VELOCITY: float = Field(ge=0, default=0)

    ALLOWED_QUEUE_SIZE: int | None = Field(default=0, ge=0)

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
        return SimulationVelocityConverter.kmh_to_meters_per_minute(v)


class RideHailingOperationsConfig(OperationsConfig):
    """Configuration for ride-hailing operations parameters."""

    # OPERATOR_TYPE: type[Operator] =

    AV_PRICE_REDUCTION: float = Field(gt=0)
    MAX_PICKUP_DISTANCE: int = Field(gt=0)
    PRICE_ENTERING: float = Field(ge=0)
    PRICE_PER_MINUTE: float = Field(ge=0)
    PRICE_PER_KM: float = Field(ge=0)
    MINIMUM_PRICE: float = Field(ge=0)


class RideHailingBaseChargingOperationsConfig(RideHailingOperationsConfig):
    """Configuration for ride-hailing base charging operations."""


class RideHailingGreedyChargingOperationsConfig(RideHailingOperationsConfig):
    """Configuration for ride-hailing greedy charging operations."""


class RideHailingUncoordinatedChargingOperationsConfig(RideHailingOperationsConfig):
    """Configuration for shared, uncoordinated charging operations."""


class RideHailingSharedChargingOperationsConfig(RideHailingOperationsConfig):
    """Configuration for shared, coordinated charging operations."""


class RideHailingMPChargingOperationsConfig(RideHailingOperationsConfig):
    """Configuration for ride-hailing multi-party charging operations."""

    # TODO add base type once we have one
    CHARGING_ALGORITHM_TYPE: type


class IntegratedSharedMobilityOperationsConfig(OperationsConfig):
    """Configuration for integrated shared mobility operations."""

    OPERATIONS_TYPE: type[Operations] = IntegratedSharedMobilityOperations

    NUMBER_OF_SERVICE_WORKERS: int = Field(gt=0)
    WORKER_COST_CONFIG: WorkerCostConfig = Field(default_factory=WorkerCostConfig)

    CHARGING_STATION_POWER: float | None = Field(default=None)
    NUMBER_OF_BASE_REGIONS: int | None = Field(default=None)
    BASE_CAPACITY: int | None = Field(default=None)
    BASE_REGIONS: list[str] | None = Field(default=None)


class OperatorConfig(ConfigBaseModel):
    """Configuration for operator parameters."""

    # TODO: https://github.com/IS3UniCologne/urban-mobility-simulation/issues/211 should go here

    # AVAILABLE_MODES: list[AutonomyType]
    # AVAILABLE_MODES_SUPPLY: list[int]
    OPERATOR_TYPE: type[Operator]

    FLEET_CONFIG: FleetConfig

    OPERATIONS_CONFIG: OperationsConfig
    SEARCH_ENGINE_CONFIG: SearchEngineConfig
    ALLOCATION_ENGINE_CONFIG: AllocationEngineConfig

    CHARGING_INFRASTRUCTURE: ChargingInfrastructureConfig | None = Field(default=None)

    # Public transit stuff
    MAX_BUSSES: int | None = Field(default=None, gt=0)


class RideHailingOperatorConfig(OperatorConfig):
    """Configuration for ride-hailing operator parameters."""

    OPERATOR_TYPE: type[Operator] = RideHailingOperator


class SharedVehicleOperatorConfig(OperatorConfig):
    """Configuration for shared vehicle operator parameters."""

    OPERATOR_TYPE: type[Operator] = SharedMobilityOperator


class SearchEngineConfig(ConfigBaseModel):
    """Configuration for search engine parameters."""

    SEARCH_ENGINE_TYPE: type[SearchEngine]


class RideHailingSearchEngineConfig(SearchEngineConfig):
    """Configuration for ride-hailing search engine parameters."""

    SEARCH_ENGINE_TYPE: type[SearchEngine] = RideHailingSearchEngine


class SharedVehicleSearchEngineConfig(SearchEngineConfig):
    """Configuration for shared vehicle search engine parameters."""

    SEARCH_ENGINE_TYPE: type[SearchEngine] = SharedVehicleSearchEngine


class AllocationEngineConfig(ConfigBaseModel):
    """Configuration for vehicle allocation engine parameters."""

    VEHICLE_ALLOCATION_ENGINE_TYPE: type[AllocationEngine]


class RideHailingAllocationEngineConfig(AllocationEngineConfig):
    """Configuration for ride-hailing vehicle allocation engine parameters."""

    VEHICLE_ALLOCATION_ENGINE_TYPE: type[AllocationEngine] = RideHailingAllocationEngine


class SharedVehicleAllocationEngineConfig(AllocationEngineConfig):
    """Configuration for shared vehicle allocation engine parameters."""

    VEHICLE_ALLOCATION_ENGINE_TYPE: type[AllocationEngine] = (
        SharedVehicleAllocationEngine
    )


class RideHailingGlobalConfig(ConfigBaseModel):
    """Global configuration for ride-hailing parameters."""


class AuctionConfig(ConfigBaseModel):
    """Configuration for auction parameters."""

    AUCTION_TYPE: type[Auction]

    AUCTION_START: int = Field(ge=0)
    AUCTION_END: int = Field(gt=0)


class SharedChargingAuctionConfig(AuctionConfig):
    """Configuration for shared charging auction parameters."""

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


class Configuration:
    """
    Configuration class for simulation parameters.

    Lazily loads and validates each configuration section only when accessed.
    Preserves type checking and IDE auto-completion for each section property.
    """

    def __init__(self, project_dir: str | Path) -> None:
        project_path = Path(project_dir)
        if not project_path.is_dir():
            raise NotADirectoryError(f"Expected a directory: {project_path}")

        config_file = project_path / "config.toml"
        if not config_file.exists():
            raise FileNotFoundError(f'Could not find "config.toml" in {project_path}')

        with open(config_file, "rb") as f:
            data = tomllib.load(f)

        self._data = {k.lower(): v for k, v in data.items()}
        self._apply_log_level_override()  # From env var, if set
        self._cache: dict[str, object] = {}
        self._project_dir: Path = project_path.resolve()

        # Load components that are configured as Python modules
        self._load_config_from_py(self._project_dir)

        self._validate_fleet_supply_files()

    def _apply_log_level_override(self) -> None:
        """Override log levels with env var, if set (from CLI)."""
        override = os.environ.get(LOG_LEVEL_ENV_VAR)
        if override is None:
            return
        override = override.strip().upper()
        if override not in VALID_LOG_LEVELS:
            logger.warning(
                "Ignoring invalid %s=%r (expected one of %s)",
                LOG_LEVEL_ENV_VAR,
                os.environ[LOG_LEVEL_ENV_VAR],
                ", ".join(sorted(VALID_LOG_LEVELS)),
            )
            return
        settings = self._data.get("settings")
        if not isinstance(settings, dict):
            return
        settings["LOG_LEVEL"] = override
        settings["FILE_LOG_LEVEL"] = override

    def _get_section(self, section: str, model: type[T]) -> T:
        if section in self._cache:
            return cast("T", self._cache[section])
        if section not in self._data:
            raise AttributeError(f"Config section '{section}' not found")
        try:
            validated_model = model.model_validate(self._data[section])
            self._cache[section] = validated_model
            return validated_model
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
            return cast("list[T]", self._cache[section])

        items = self._data.get(section)
        result: list[T]
        if items is None:
            result = []
        else:
            result = [model.model_validate(item) for item in items]

        self._cache[section] = result
        return result

    def _get_section_dict(self, section: str, model: type[T]) -> dict[str, T]:
        """Get a section that contains a dictionary of items."""
        return self._get_optional_section_dict(section, model) or {}

    def _get_optional_section_dict(
        self, section: str, model: type[T]
    ) -> dict[str, T] | None:
        """Get a section dict, or None if the section is absent."""
        if section in self._cache:
            return cast("dict[str, T] | None", self._cache[section])

        items = self._data.get(section)
        result: dict[str, T] | None = (
            None
            if items is None
            else {k: model.model_validate(v) for k, v in items.items()}
        )

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
        if "path" not in self._cache:
            self._cache["path"] = PathConfig.from_raw(
                self._data["path"], self._project_dir
            )
        return cast("PathConfig", self._cache["path"])

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
    def operators(self) -> list[OperatorConfig]:
        """
        Get the operators configuration section.

        Returns
        -------
        list[OperatorConfig]
            The operators configuration section.
        """
        return self._get_section_list("operator", OperatorConfig)

    def all_supply_distribution_paths(self) -> list[Path]:
        """Return every supply parquet that contributes hex IDs to the simulation.

        Includes per-fleet ``SUPPLY_DISTRIBUTION_FILE`` overrides as well as
        the dataset-level ``supply.parquet``.
        Order is preserved, duplicates are removed.

        Returns
        -------
        list of Path
            Paths to supply distribution files.
        """
        paths: list[Path] = []
        seen: set[Path] = set()
        for op in self.operators:
            path = op.FLEET_CONFIG.supply_distribution_path(self.path.PROJECT_DIR)
            if path is not None and path not in seen:
                paths.append(path)
                seen.add(path)
        dataset_supply = self.path.supply
        if dataset_supply is not None and dataset_supply not in seen:
            paths.append(dataset_supply)
        return paths

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
        return self._get_optional_section_dict("transit_vehicles", VehicleConfig)

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
        """Load configuration from Python module files."""
        # Define files to load: (filename, required)
        config_files = [("operators.py", True), ("population.py", True)]

        # Map model types to their config section names
        model_to_section: dict[type[BaseModel], str] = {
            OperatorConfig: "operator",
            PopulationConfig: "population",
        }
        model_classes = tuple(model_to_section.keys())

        # Collect instances from all files
        section_buckets: dict[str, list[BaseModel]] = {
            section: [] for section in set(model_to_section.values())
        }

        for filename, required in config_files:
            file_path = base_path / filename
            if not file_path.exists():
                if required:
                    raise FileNotFoundError(
                        f'Could not find required configuration file "{filename}" in {base_path}'
                    )
                continue

            module = self._import_module_file(file_path)

            # Collect config instances from this module
            for name, value in vars(module).items():
                if name.startswith("_"):
                    continue
                self._collect_config_instance(
                    value, model_classes, model_to_section, section_buckets
                )

        # Store collected instances in cache
        self._cache["operator"] = section_buckets.get("operator", [])
        population_configs = section_buckets.get("population", [])
        if len(population_configs) == 0:
            raise ValueError("No PopulationConfig instance found in population.py. ")
        if len(population_configs) > 1:
            raise ValueError(
                "Multiple PopulationConfig instances found in population.py. "
            )
        self._cache["population"] = population_configs[0]

    def _validate_fleet_supply_files(self) -> None:
        """Raise if any fleet references a SUPPLY_DISTRIBUTION_FILE that does not exist."""
        for op in self.operators:
            path = op.FLEET_CONFIG.supply_distribution_path(self._project_dir)
            if path is not None and not path.exists():
                raise FileNotFoundError(
                    f"Supply distribution file '{op.FLEET_CONFIG.SUPPLY_DISTRIBUTION_FILE}' "
                    f"not found in project directory {self._project_dir}"
                )

    def _collect_config_instance(
        self,
        obj: object,
        model_classes: tuple[type[BaseModel], ...],
        model_to_section: dict[type[BaseModel], str],
        section_buckets: dict[str, list[BaseModel]],
    ) -> None:
        """Recursively collect config instances from an object."""
        if isinstance(obj, model_classes):
            for cls, section in model_to_section.items():
                if isinstance(obj, cls):
                    section_buckets[section].append(obj)
                    return
        # Recurse into containers
        if isinstance(obj, list | tuple):
            for elem in obj:
                self._collect_config_instance(
                    elem, model_classes, model_to_section, section_buckets
                )

    def _import_module_file(self, file_path: Path) -> ModuleType:
        """Import a module from a filesystem .py file path."""
        spec = importlib.util.spec_from_file_location("ums_py_config", file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for {file_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
