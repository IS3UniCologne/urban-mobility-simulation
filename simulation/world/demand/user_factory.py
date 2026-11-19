"""User creation factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.agent.user.choice_model import ChoiceModelInterface
from simulation.agent.user.choice_model.choice_model_interface import (
    ChoiceModelDependencies,
)
from simulation.agent.user.user import User
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.simulation_base import SimulationBase

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import UserConfig
    from simulation.helper.types import RegionId
    from simulation.world.world import World


class UserFactory(SimulationBase):
    """Factory module for creating new users.

    Parameters
    ----------
    sim : SimulationContext
        The active simulation context instance.
    world : World
        The world instance containing state and services used during simulation.
    """

    def __init__(self, sim: SimulationContext, world: World) -> None:
        super().__init__(sim)
        self._sim = sim
        self._world = world
        self._config = sim.config
        self._geo_env = sim.geo_env
        self._rng = sim.random_manager.get_rng("USER_FACTORY")
        # Keyed by identity, since a configuration model has no hash (the population keeps every user configuration alive)
        self._choice_models: dict[int, ChoiceModelInterface] = {}

    def create_user(
        self,
        origin_region: RegionId,
        destination_region: RegionId,
        user_config: UserConfig,
    ) -> User:
        """
        Create a user.

        User will spawn in a random position within the given origin region,
        with a transport task to a random position within the given destination region.

        Parameters
        ----------
        origin_region : RegionId
            The origin spatial unit ID (e.g., hexagon ID).
        destination_region : RegionId
            The destination spatial unit ID (e.g., hexagon ID).
        user_config : UserConfig
            Configuration for the user.

        Returns
        -------
        User
            The created user instance.
        """
        # Get Origin and Destination positions
        origin_lat, origin_lng = self._geo_env.get_random_position(
            hex_id=origin_region, layer_name="hex"
        )
        destination_lat, destination_lng = self._geo_env.get_random_position(
            hex_id=destination_region, layer_name="hex"
        )

        origin_position = GeodesicPosition(self._sim, origin_lat, origin_lng)
        destination_position = GeodesicPosition(
            self._sim, destination_lat, destination_lng
        )

        user = User(
            sim=self._sim,
            user_config=user_config,
            user_log=self._world.user_log,
            origin=origin_position,
            destination=destination_position,
            mobility_search_engine=self._world.mobility_search,
            choice_model=self._choice_model(user_config),
        )

        self.logger.debug(
            "Created user %s from %s to %s", user.uid, origin_region, destination_region
        )

        return user

    def _choice_model(self, user_config: UserConfig) -> ChoiceModelInterface:
        """Return the choice model that every user of one configuration shares."""
        choice_model = self._choice_models.get(id(user_config))
        if choice_model is None:
            choice_model = ChoiceModelInterface.from_deps(
                deps=ChoiceModelDependencies(
                    sim=self._sim, choice_model_config=user_config.CHOICE_MODEL_CONFIG
                )
            )
            self._choice_models[id(user_config)] = choice_model
        return choice_model
