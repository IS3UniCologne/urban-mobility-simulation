"""User creation factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.agent.user.user import User
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.enums import VehicleType
from simulation.helper.simulation_base import SimulationBase
from simulation.tasks.transport_task import TransportTask

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import UserConfig
    from simulation.helper.types import RegionId
    from simulation.world.world import World


class UserFactory(SimulationBase):
    """Factory for creating mobility users and their transport tasks."""

    def __init__(self, sim: SimulationContext, world: World) -> None:
        super().__init__(sim)
        self._sim = sim
        self._world = world
        self._config = sim.config
        self._geo_env = sim.geo_env
        self._rng = sim.random_manager.get_rng("USER_FACTORY")

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
            hex_id=origin_region,
            layer_name=f"hex_{self._config.world.SPATIAL_RESOLUTION}",
        )
        destination_lat, destination_lng = self._geo_env.get_random_position(
            hex_id=destination_region,
            layer_name=f"hex_{self._config.world.SPATIAL_RESOLUTION}",
        )

        origin_position = GeodesicPosition(self._sim, origin_lat, origin_lng)
        destination_position = GeodesicPosition(
            self._sim, destination_lat, destination_lng
        )

        # TODO: Implement proper filtering criteria in user config
        viable_vehicle_types = {vt: 1 for vt in VehicleType}

        transport_task = TransportTask(
            time=self._sim.env.now,
            origin=origin_position,
            destination=destination_position,
            viable_vehicle_types=viable_vehicle_types,
        )

        # TODO: Choice model deps
        choice_model = user_config.CHOICE_MODEL_CONFIG.CHOICE_MODEL_TYPE(self._sim)

        user = User(
            sim=self._sim,
            position=origin_position,
            transport_task=transport_task,
            mobility_search_engine=self._world.mobility_search,
            choice_model=choice_model,
        )

        self.logger.debug(
            "Created user %s from %s to %s", user.uid, origin_region, destination_region
        )

        return user
