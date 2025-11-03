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
    WALKING_SPEED=5.0,  # km/h
    CHOICE_MODEL_CONFIG=RandomModeNearestVehicleChoiceModelConfig(),
)

user2 = UserConfig(
    TRANSIT_MAX_WAIT=15,
    SPATIAL_STRATEGY="nearest",
    WALKING_SPEED=5.5,  # km/h not so fast!
    CHOICE_MODEL_CONFIG=RandomModeNearestVehicleChoiceModelConfig(),
)


POPULATION = PopulationConfig(
    SEGMENTS=[
        PopulationSegmentConfig(PROPORTION=0.5, USER_CONFIG=user1),
        PopulationSegmentConfig(PROPORTION=0.5, USER_CONFIG=user2),
    ]
)
