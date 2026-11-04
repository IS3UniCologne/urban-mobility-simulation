"""
Demand generation factory.

This module provides the DemandFactory class, which generates and manages demand
based on spatio-temporal demand profiles and configurable modifiers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import geojson
import h3
import numpy
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

    _SliceKey = tuple[RegionId, int, bool]


@dataclass(frozen=True, slots=True)
class _DemandSlice:
    """Arrival rate (per time bucket) and destination distribution of one origin, time bucket and day type."""

    arrival_rate: float
    destinations: list[RegionId]
    destination_probabilities: numpy.ndarray


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
    _modifiers : list of str
        Paths to GeoJSON files containing demand modifiers.
    _modifiers : dict
        Mapping of spatial unit IDs to demand multipliers.
    _demand_slices : dict
        Demand slice per origin, time bucket and non-working day with demand.
    _spatial_units : list of str
        List of unique spatial unit IDs.
    _rng : numpy.random.Generator
        Random number generator for demand sampling.
    _population_segments : list of PopulationSegmentConfig
        Population segments new users are drawn from.
    _segment_proportions : list of float
        Share of new users per population segment, in segment order.
    _user_factory : UserFactory
        Factory for creating users.

    Methods
    -------
    generate_demand()
        Starts demand generation processes for all spatial units.
    spawn_demand_process(spatial_unit: str)
        Generator for demand events in a specific spatial unit.
    reset()
        Resets the demand factory and clears all demand-related state.
    """

    __slots__ = (
        "_config",
        "_daily_resolution",
        "_demand_slices",
        "_env",
        "_modifiers",
        "_population_segments",
        "_rng",
        "_segment_proportions",
        "_spatial_resolution",
        "_spatial_units",
        "_temporal_resolution",
        "_time",
        "_user_factory",
        "_world",
    )

    def __init__(self, sim: SimulationContext, world: World) -> None:
        super().__init__(sim)

        self._config = sim.config
        self._env = sim.env
        self._time = SimulationTime(sim.env)
        self._world: World = world

        self._temporal_resolution = self._config.world.TEMPORAL_RESOLUTION
        self._spatial_resolution = self._config.world.SPATIAL_RESOLUTION
        self._daily_resolution = self._config.world.DAILY_RESOLUTION

        self._modifiers = {}

        demand_profile = self._load_demand_profile()
        self._demand_slices: dict[_SliceKey, _DemandSlice] = self._index_demand_profile(
            demand_profile
        )
        self._spatial_units = list(demand_profile[demand_schema.ORIGIN].unique())

        self._rng = sim.random_manager.get_rng("DEMANDFACTORY")
        self._population_segments = self._config.population.SEGMENTS
        self._segment_proportions = [
            segment.PROPORTION for segment in self._population_segments
        ]

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

    @staticmethod
    def _index_demand_profile(profile: DataFrame) -> dict[_SliceKey, _DemandSlice]:
        """Group the demand profile rows by origin, time bucket and non-working day.

        Rows with a zero arrival rate are dropped, so a missing slice means no demand.
        """
        profile = profile[profile[demand_schema.ORIGIN_ARRIVAL_RATE] > 0]
        arrival_rates = profile[demand_schema.ORIGIN_ARRIVAL_RATE].to_numpy()
        probabilities = profile[demand_schema.DESTINATION_PROBABILITY].to_numpy()
        # Slices share one string object per destination (one per row held about 60 MB on the e2e datasets)
        destination_codes, unique_destinations = profile[
            demand_schema.DESTINATION
        ].factorize(use_na_sentinel=False)
        destination_names = numpy.asarray(unique_destinations, dtype=object)
        rows_by_key = cast(
            "dict[_SliceKey, numpy.ndarray]",
            profile.groupby(
                [
                    demand_schema.ORIGIN,
                    demand_schema.TIME_BUCKET,
                    demand_schema.IS_WEEKEND,
                ],
                sort=False,
            ).indices,
        )
        return {
            key: _DemandSlice(
                arrival_rate=arrival_rates[rows[0]],
                destinations=destination_names[destination_codes[rows]].tolist(),
                destination_probabilities=probabilities[rows],
            )
            for key, rows in rows_by_key.items()
        }

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
        # Run until simulation ends
        while True:
            try:
                # Transform current time to temporal buckets as defined in the demand profile
                time_bucket = SimulationTimeConverter.convert_to_temporal_bucket(
                    self._time.now(), self._temporal_resolution
                )
                non_working_day = SimulationTimeConverter.convert_to_day_of_week_bucket(
                    self._time.now()
                )

                key: _SliceKey = (spatial_unit, int(time_bucket), non_working_day)
                demand_slice = self._demand_slices.get(key)
                if demand_slice is None:
                    # No slice means no arrivals in the sample, so wait for the next time bucket
                    self.logger.debug(
                        "Hex: %s  Time: %s  Date:%s  Env Time: %s",
                        spatial_unit,
                        time_bucket,
                        non_working_day,
                        self._time.now(),
                    )
                    bucket_in_minutes = self._temporal_resolution * 60
                    time_to_next_bucket = bucket_in_minutes - (
                        self._time.now() % bucket_in_minutes
                    )
                    yield self._env.timeout(time_to_next_bucket)
                    continue

                modifier = self._modifiers.get(spatial_unit, 1.0)
                if modifier == 0:
                    self.logger.debug(
                        "Spatial unit %s is removed from demand generation process",
                        spatial_unit,
                    )
                    break

                # TODO: is this a viable way of modifying exponential sampling using the scale factor?
                # TODO: if we wait for longer than the timebucket is long, we should probably consider no demand (otherwise we spawn this in the next timebucket and skew the real demand distribution)
                inter_arrival_time = self._rng.exponential(
                    1.0 / demand_slice.arrival_rate / modifier
                ) * float(self._temporal_resolution * 60)
                yield self._env.timeout(inter_arrival_time)

                destination_index = self._rng.multinomial(
                    1, demand_slice.destination_probabilities
                ).argmax()
                destination = demand_slice.destinations[destination_index]
                self._create_user(spatial_unit, destination)
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
        # Choosing an index keeps numpy from probing every pydantic segment for array protocols on each call
        index = self._rng.choice(
            len(self._population_segments), p=self._segment_proportions
        )
        return self._population_segments[index]
