from simulation.helper.configuration.configuration import (
    PopulationConfig,
    PopulationSegmentConfig,
    RandomModeNearestVehicleChoiceModelConfig,
    UserConfig,
)

user_config_slow = UserConfig(
    TRANSIT_MAX_WAIT=10,
    SPATIAL_STRATEGY="hexagon",
    WALKING_SPEED_KMH=3.0,
    MAX_SEARCH_DURATION_MIN=5,
    CHOICE_MODEL_CONFIG=RandomModeNearestVehicleChoiceModelConfig(),
)

user_config_avg = UserConfig(
    TRANSIT_MAX_WAIT=10,
    SPATIAL_STRATEGY="hexagon",
    WALKING_SPEED_KMH=5.0,
    MAX_SEARCH_DURATION_MIN=10,
    CHOICE_MODEL_CONFIG=RandomModeNearestVehicleChoiceModelConfig(),
)

user_config_fast = UserConfig(
    TRANSIT_MAX_WAIT=10,
    SPATIAL_STRATEGY="hexagon",
    WALKING_SPEED_KMH=6.0,
    MAX_SEARCH_DURATION_MIN=15,
    CHOICE_MODEL_CONFIG=RandomModeNearestVehicleChoiceModelConfig(),
)

POPULATION = PopulationConfig(
    SEGMENTS=[
        PopulationSegmentConfig(PROPORTION=0.2, USER_CONFIG=user_config_slow),
        PopulationSegmentConfig(PROPORTION=0.3, USER_CONFIG=user_config_avg),
        PopulationSegmentConfig(PROPORTION=0.5, USER_CONFIG=user_config_fast),
    ]
)
