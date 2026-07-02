"""Population configuration."""

from __future__ import annotations

from simulation.helper.configuration.configuration import (
    PopulationConfig,
    PopulationSegmentConfig,
    RandomModeNearestVehicleChoiceModelConfig,
    UserConfig,
)

user1 = UserConfig(
    TRANSIT_MAX_WAIT=15,
    SPATIAL_STRATEGY="nearest",
    WALKING_SPEED_KMH=5.0,
    MAX_SEARCH_DURATION_MIN=10,
    CHOICE_MODEL_CONFIG=RandomModeNearestVehicleChoiceModelConfig(),
)

user2 = UserConfig(
    TRANSIT_MAX_WAIT=15,
    SPATIAL_STRATEGY="nearest",
    WALKING_SPEED_KMH=5.5,
    MAX_SEARCH_DURATION_MIN=10,
    CHOICE_MODEL_CONFIG=RandomModeNearestVehicleChoiceModelConfig(),
)

POPULATION = PopulationConfig(
    SEGMENTS=[
        PopulationSegmentConfig(PROPORTION=0.5, USER_CONFIG=user1),
        PopulationSegmentConfig(PROPORTION=0.5, USER_CONFIG=user2),
    ]
)
