"""Unit tests for the user agent."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
import simpy

from simulation.agent.user.choice_model import ChoiceModelInterface
from simulation.agent.user.choice_model.choice_model_interface import (
    ChoiceModelDependencies,
)
from simulation.agent.user.user import User
from simulation.helper.configuration.configuration import ChoiceModelConfig, UserConfig
from simulation.helper.random.random_manager import RandomManager
from simulation.operator.data_transfer_object.transportation_alternative import (
    TransportationAlternative,
)
from simulation.operator.data_transfer_object.transportation_alternative_browser import (
    TransportationAlternativeBrowser,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Timeout

    from simulation.helper.enums import OperatorMode, VehicleType

pytestmark = pytest.mark.unit


class EqualChoiceModelStub(ChoiceModelInterface):
    """Choice model that gives every alternative the same probability."""

    def calculate_choice_probabilities(
        self, user: User, available_alternatives: TransportationAlternativeBrowser
    ) -> dict[TransportationAlternative, float]:
        alternatives = available_alternatives.transportation_alternatives
        return {alternative: 1 / len(alternatives) for alternative in alternatives}

    @property
    def accepted_vehicle_types(self) -> frozenset[VehicleType]:
        return frozenset()

    @property
    def accepted_operator_modes(self) -> frozenset[OperatorMode]:
        return frozenset()


class FailingAllocationEngineStub:
    """Allocation engine that records the price of each requested alternative and allocates no vehicle."""

    def __init__(self, env: simpy.Environment) -> None:
        self._env = env
        self.requested_prices: list[float] = []

    def request_vehicle_allocation(
        self, user: User, alternative: TransportationAlternative
    ) -> Generator[Timeout, None, None]:
        self.requested_prices.append(alternative.price)
        yield self._env.timeout(0)


def attempt_order(seed: int, alternative_count: int) -> list[float]:
    """Run one user over equally likely alternatives and return their prices in the order attempted."""
    env = simpy.Environment()
    sim = Mock()
    sim.env = env
    sim.config.random_manager.SEED = seed
    sim.config.random_manager.COMPONENT_SEEDS = {}
    sim.uid_manager.generate_uid.return_value = (1, "User_1")
    sim.random_manager = RandomManager(sim)

    engine = FailingAllocationEngineStub(env)
    browser = TransportationAlternativeBrowser()
    for price in range(alternative_count):
        # Fresh mocks hash by identity, as Route and the operators do in a simulation
        browser.add_transportation_alternative(
            TransportationAlternative(
                vehicle=Mock(),
                route=Mock(),
                price=float(price),
                duration=1.0,
                distance=1.0,
                convenience=1.0,
                operator=Mock(allocation_engine=engine),
            )
        )
    search_engine = Mock()
    search_engine.search_for_transportation_alternatives.return_value = browser

    choice_model_config = ChoiceModelConfig(CHOICE_MODEL_TYPE=EqualChoiceModelStub)
    user_config = UserConfig(
        TRANSIT_MAX_WAIT=10,
        SPATIAL_STRATEGY="hexagon",
        WALKING_SPEED_KMH=5.0,
        MAX_SEARCH_DURATION_MIN=1,
        CHOICE_MODEL_CONFIG=choice_model_config,
    )
    choice_model = EqualChoiceModelStub(
        ChoiceModelDependencies(sim=sim, choice_model_config=choice_model_config)
    )
    user = User(sim, user_config, Mock(), Mock(), Mock(), search_engine, choice_model)
    user.start()
    env.run()
    return engine.requested_prices


def test_same_seed_tries_alternatives_in_same_order() -> None:
    first = attempt_order(seed=42, alternative_count=8)
    second = attempt_order(seed=42, alternative_count=8)

    assert set(first) == {float(price) for price in range(8)}
    assert first == second
