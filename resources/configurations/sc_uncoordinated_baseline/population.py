"""Simple population configuration for testing."""

from simulation.helper.configuration.configuration import (
    PopulationConfig,
    PopulationSegmentConfig,
    RandomModeNearestVehicleChoiceModelConfig,
    UserConfig,
)

user1 = UserConfig(
    TRANSIT_MAX_WAIT=15,
    SPATIAL_STRATEGY="nearest",
    WALKING_SPEED_KMH=5.0,  # km/h
    MAX_SEARCH_DURATION_MIN=10,
    CHOICE_MODEL_CONFIG=RandomModeNearestVehicleChoiceModelConfig(),
)


POPULATION = PopulationConfig(
    SEGMENTS=[PopulationSegmentConfig(PROPORTION=1.0, USER_CONFIG=user1)]
)
