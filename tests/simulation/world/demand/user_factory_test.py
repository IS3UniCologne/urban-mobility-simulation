"""Unit tests for the user factory."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
import simpy

from simulation.agent.user.choice_model import ChoiceModelInterface
from simulation.helper.configuration.configuration import ChoiceModelConfig, UserConfig
from simulation.world.demand.user_factory import UserFactory

if TYPE_CHECKING:
    from simulation.agent.user.choice_model.choice_model_interface import (
        ChoiceModelDependencies,
    )
    from simulation.agent.user.user import User
    from simulation.helper.enums import OperatorMode, VehicleType
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )
    from simulation.operator.data_transfer_object.transportation_alternative_browser import (
        TransportationAlternativeBrowser,
    )

pytestmark = pytest.mark.unit


class RecordingChoiceModelStub(ChoiceModelInterface):
    """Choice model that records its configuration on the simulation context."""

    def __init__(self, deps: ChoiceModelDependencies) -> None:
        super().__init__(deps)
        deps.sim.choice_model_configs.append(deps.choice_model_config)

    def calculate_choice_probabilities(
        self, user: User, available_alternatives: TransportationAlternativeBrowser
    ) -> dict[TransportationAlternative, float]:
        return {}

    @property
    def accepted_vehicle_types(self) -> frozenset[VehicleType]:
        return frozenset()

    @property
    def accepted_operator_modes(self) -> frozenset[OperatorMode]:
        return frozenset()


def user_config() -> UserConfig:
    return UserConfig(
        TRANSIT_MAX_WAIT=10,
        SPATIAL_STRATEGY="hexagon",
        WALKING_SPEED_KMH=5.0,
        MAX_SEARCH_DURATION_MIN=1,
        CHOICE_MODEL_CONFIG=ChoiceModelConfig(
            CHOICE_MODEL_TYPE=RecordingChoiceModelStub
        ),
    )


def test_users_of_one_configuration_share_a_choice_model() -> None:
    sim = Mock()
    sim.env = simpy.Environment()
    sim.config.world.SPATIAL_RESOLUTION = 7
    sim.uid_manager.generate_uid.return_value = (1, "Stub_1")
    sim.geo_env.get_random_position.return_value = (52.5, 13.4)
    sim.choice_model_configs = []
    factory = UserFactory(sim, Mock())
    first_config, second_config = user_config(), user_config()

    for config in (first_config, first_config, second_config):
        factory.create_user("origin", "destination", config)

    first_created, second_created = sim.choice_model_configs
    assert first_created is first_config.CHOICE_MODEL_CONFIG
    assert second_created is second_config.CHOICE_MODEL_CONFIG
