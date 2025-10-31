from __future__ import annotations

from simulation.helper.configuration.configuration import (
    RandomModeNearestVehicleChoiceModelConfig,
    UserConfig,
)

choice_model1 = RandomModeNearestVehicleChoiceModelConfig()

user1 = UserConfig(
    TRANSIT_MAX_WAIT=15,  # minutes
    SPATIAL_STRATEGY="nearest",
    WALKING_SPEED=4.8,  # km/h (converted to meters/min by validator)
    CHOICE_MODEL_CONFIG=choice_model1,
)
