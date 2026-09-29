"""
Demand generation factory.

This module provides the DemandFactory class, which generates and manages demand
based on spatio-temporal demand profiles and configurable modifiers.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import geojson
import h3
import simpy

from simulation.helper.simulation_base import SimulationBase
from simulation.helper.time import SimulationTime, SimulationTimeConverter
from simulation.world.demand import demand_schema
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.demand.user_factory import UserFactory

if TYPE_CHECKING:
    from collections.abc import Generator

    from pandas import DataFrame

    from simulation.context.simulation_context import SimulationContext
    from simulation.helper.configuration.configuration import PopulationSegmentConfig
    from simulation.helper.types import RegionId
    from simulation.world.world import World


class DemandFactory(SimulationBase):
    """
    Factory for generating and managing demand based on spatio-temporal demand profiles and configurable modifiers.

    This class loads demand profiles, applies modifiers, and spawns demand generation processes
    for each spatial unit in the simulation environment.

    Attributes
    ----------
    _config : Configuration
        The configuration instance containing simulation settings.
    _env : simpy.Environment
        The simulation environment.
    _time : SimulationTime
        The simulation time manager.
    _world : World
        The simulation world instance.
    _maximal_demand : int
        Maximum number of demand events to generate.
    _modifiers : dict
        Mapping of spatial unit IDs to demand multipliers.
    _demand_profile : DataFrame
        The loaded demand profile data.
    _spatial_units : list of str
        List of unique spatial unit IDs.
    _rng : numpy.random.Generator
        Random number generator for demand sampling.
    _user_factory : UserFactory
        Factory for creating users.
    """

    __slots__ = (
        "_config",
        "_daily_resolution",
        "_demand_profile",
        "_env",
        "_maximal_demand",
        "_modifiers",
        "_rng",
        "_spatial_resolution",
        "_spatial_units",
        "_temporal_resolution",
        "_time",
        "_user_factory",
        "_world",
    )
    counter = 0

    def __init__(
        self,
        sim: SimulationContext,
        world: World,
        maximal_demand=3_000_000,  # noqa: ANN001
    ) -> None:
        super().__init__(sim)

        self._config = sim.config
        self._env = sim.env
        self._time = SimulationTime(sim.env)
        self._world: World = world

        self._temporal_resolution = self._config.world.TEMPORAL_RESOLUTION
        self._spatial_resolution = self._config.world.SPATIAL_RESOLUTION
        self._daily_resolution = self._config.world.DAILY_RESOLUTION

        self._maximal_demand = maximal_demand
        self._modifiers = {}

        self._demand_profile = self._load_demand_profile()
        self._spatial_units = list(self._demand_profile[demand_schema.ORIGIN].unique())

        self._rng = sim.random_manager.get_rng("DEMANDFACTORY")

        self._user_factory = UserFactory(sim, world)

        self._load_modifiers()

    def _load_demand_profile(self) -> DataFrame:
        """Load the demand profile from the configured path using the DemandImporter."""
        demand_importer = DemandImporter(
            temporal_resolution=self._temporal_resolution,
            spatial_resolution=self._spatial_resolution,
            daily_resolution=self._daily_resolution,
        )
        return demand_importer.load(self._config.path.demand)

    def _register_modifier(self, geomodifier) -> None:  # noqa: ANN001
        multiplier = geomodifier["properties"]["demandMultiplier"]
        hex_ids = h3.polygon_to_cells(
            h3.geo_to_h3shape(geomodifier["geometry"]), res=self._spatial_resolution
        )
        # TODO: this currently allows for overlapping modifiers, which will be applied sequentially (last one wins). I added a warning, but is this even desired behaviour?
        for hex_id in hex_ids:
            existing = self._modifiers.get(hex_id)
            if existing is not None and existing != multiplier:
                self.logger.warning(
                    "Demand modifier overlap at hex %s: %.3f overwriting %.3f",
                    hex_id,
                    multiplier,
                    existing,
                )
            self._modifiers[hex_id] = multiplier

    def _load_modifiers(self) -> None:
        """Load and register per-hexagon demand modifiers from PROJECT_DIR/demand_modifiers/."""
        paths = self._config.path.demand_modifiers
        if not paths:
            self.logger.info("No demand modifiers found, skipping.")
            return

        for path in paths:
            try:
                with open(path) as f:
                    geo = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                self.logger.warning('Skipping "%s": %s', path, e)
                continue

            if not geojson.loads(json.dumps(geo)).is_valid:
                self.logger.warning('Skipping "%s": not valid GeoJSON.', path)
                continue

            features = geo.get("features", [geo])
            for feature in features:
                self._register_modifier(feature)
            self.logger.info(
                "Loaded demand modifier %s (%d features).", path.name, len(features)
            )

    def generate_demand(self):  # noqa: ANN201
        """Invoke for each spatial unit a dedicated process which generates demand."""
        spawned = self._env.event()

        for unit in self._spatial_units:
            self._world.demand_processes.append(
                self._env.process(self.spawn_demand_process(unit))
            )

        yield spawned.succeed()

    def spawn_demand_process(
        self, spatial_unit: str
    ) -> Generator[simpy.Timeout, Any, None]:
        """Spawn a demand generator on given spatial unit.

        Parameters
        ----------
        spatial_unit : str
            The hexagon ID of the spatial unit for which to spawn the demand generator.

        Yields
        ------
        simpy.Timeout
            A timeout until the next demand is generated based on the demand profile.
        """
        # Filter data on spatial unit such that we don't need to filter on the entire demand profile
        local_demand_profile = self._demand_profile[
            (self._demand_profile[demand_schema.ORIGIN] == spatial_unit)
        ]
        # local_demand_profile.loc[:,'o_poisson_est'] /= 4
        # Run until simulation ends
        while DemandFactory.counter < self._maximal_demand:
            try:
                # Transform current time to temporal buckets as defined in the demand profile
                time_bucket = SimulationTimeConverter.convert_to_temporal_bucket(
                    self._time.now(), self._temporal_resolution
                )
                non_working_day = SimulationTimeConverter.convert_to_day_of_week_bucket(
                    self._time.now()
                )

                # Filter demand profile on current time
                demand_slice = local_demand_profile[
                    (local_demand_profile[demand_schema.TIME_BUCKET] == time_bucket)
                    & (
                        local_demand_profile[demand_schema.IS_WEEKEND]
                        == non_working_day
                    )
                ]
                if demand_slice.shape[0] == 0:
                    self.logger.debug(
                        "Hex: %s  Time: %s  Date:%s  Env Time: %s",
                        spatial_unit,
                        time_bucket,
                        non_working_day,
                        self._time.now(),
                    )
                    # no lambda for given demand slice means there were no arrivals in the sample (lambda was zero)
                    poisson_lambda = 0
                else:
                    # Extract Poisson Estimate for given spatio-temporal cell
                    poisson_lambda = demand_slice.iloc[0][
                        demand_schema.ORIGIN_ARRIVAL_RATE
                    ]

                # Based on Poisson Estimate sample next arrival time (in minutes)
                # inter_arrival_time = numpy.random.exponential(
                #    1.0 / poisson_lambda) * self._demand_importer._get_temporal_duration_in_hours() * 60

                if poisson_lambda == 0:
                    # lambda is zero, waiting until next timebucket is reached
                    bucket_in_minutes = self._temporal_resolution * 60
                    time_to_next_bucket = bucket_in_minutes - (
                        self._time.now() % bucket_in_minutes
                    )
                    yield self._env.timeout(time_to_next_bucket)
                    continue
                else:
                    try:
                        if self._modifiers[spatial_unit] == 0:
                            self.logger.debug(
                                "Spatial unit %s is removed from demand generation process",
                                spatial_unit,
                            )
                            break

                        # TODO: is this a viable way of modifying exponential sampling using the scale factor?
                        # TODO: if we wait for longer than the timebucket is long, we should probably consider no demand (otherwise we spawn this in the next timebucket and skew the real demand distribution)
                        inter_arrival_time = self._rng.exponential(
                            1.0 / poisson_lambda / self._modifiers[spatial_unit]
                        ) * float(self._temporal_resolution * 60)
                    except KeyError:
                        # no modifier is registered for that spatial unit
                        inter_arrival_time = self._rng.exponential(
                            1.0 / poisson_lambda
                        ) * float(self._temporal_resolution * 60)

                    # await next arrival
                    yield self._env.timeout(inter_arrival_time)

                    # Sample Destination
                    prob_array = demand_slice[
                        demand_schema.DESTINATION_PROBABILITY
                    ].to_numpy()

                    # TODO: rename - this has nothing to do with low SOC
                    low_soc_vehicle_sample = self._rng.multinomial(
                        1, prob_array
                    )  # No of vehicles to be charged

                    idx = low_soc_vehicle_sample.argmax()

                    destination = demand_slice.iloc[idx][demand_schema.DESTINATION]

                    # Create and add user to world
                    self._create_user(spatial_unit, destination)

                # Increase global counter (not thread safe)
                DemandFactory.counter += 1
            except simpy.Interrupt:
                break

    def _create_user(
        self, origin_region: RegionId, destination_region: RegionId
    ) -> None:
        """
        Create a user, add them to the world and start their lifecycle process.

        Selects a population segment randomly based on configured proportions.

        Parameters
        ----------
        origin_region : RegionId
            The origin spatial region ID.
        destination_region : RegionId
            The destination spatial region ID.
        """
        # Select population segment based on proportions
        segment = self._select_segment_for_demand()

        # Create user from selected segment
        user = self._user_factory.create_user(
            origin_region=origin_region,
            destination_region=destination_region,
            user_config=segment.USER_CONFIG,
        )

        self._world.add_user(user)

        # Start user process
        user.start()

        self.logger.debug(
            "Demand generated from hexagon %s to %s. User %s",
            origin_region,
            destination_region,
            user.uid,
        )

    def _select_segment_for_demand(self) -> PopulationSegmentConfig:
        population_config = self._config.population
        segment_proportions = [
            segment.PROPORTION for segment in population_config.SEGMENTS
        ]
        return self._rng.choice(population_config.SEGMENTS, p=segment_proportions)
