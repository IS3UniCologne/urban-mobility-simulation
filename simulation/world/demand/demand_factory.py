import json
import logging

import h3
import numpy as np
import simpy

from simulation.helper.configuration.configuration import Configuration
from simulation.helper.random.random_manager import RandomManager
from simulation.helper.time import SimulationTime, SimulationTimeConverter
from simulation.world.demand.demand_importer import DemandImporter
from simulation.world.world import World


class DemandFactory:
    counter = 0

    def __init__(
        self,
        env,
        demand_profile,
        demand_importer: DemandImporter,
        world: World,
        modifiers,
        mode,
        maximal_demand=3_000_000,
    ):
        self._env = env
        self._time = SimulationTime(env)
        self._demand_profile = demand_profile
        self._demand_importer = demand_importer
        self._world = world
        self._mode = mode

        origin, destination = demand_importer._get_spatial_column()
        temporal = demand_importer._get_temporal_column()
        day_of_week_column = demand_importer._get_day_of_week_column()

        self._origin_column = origin
        self._destination_column = destination
        self._temporal_column = temporal
        self._day_of_week_column = day_of_week_column

        self._maximal_demand = maximal_demand

        self._modifier_paths = modifiers
        self._modifiers = {}

        self._spatial_units = list(self._demand_profile[origin].unique())

        # Random Number Generators
        self._rng = RandomManager().get_rng("DEMANDFACTORY")

        # Config
        self._config = Configuration()

        self._load_modifiers()

    def _register_modifier(self, geomodifier):
        multiplier = geomodifier["properties"]["demandMultiplier"]
        hex_ids = h3.polyfill(
            geomodifier["geometry"],
            res=self._config.world.SPATIAL_RESOLUTION_VALUE,
            geo_json_conformant=True,
        )

        self._modifiers.update({x: multiplier for x in hex_ids})

    def _load_modifiers(self):
        """
        Loads and registers per-hexagon demand modifiers (floating number multiplier) from GeoJSON
        """
        for modifier in self._modifier_paths:
            try:
                with open(modifier, "r") as f:
                    geo = json.load(f)
            except FileNotFoundError:
                logging.warning(
                    f'Demand modifier at "{modifier}" doesn\'t exist, skipping.'
                )
                continue

            featurecollection = True if "features" in geo else False

            if featurecollection:
                for feature in geo["features"]:
                    self._register_modifier(feature)
            else:
                self._register_modifier(geo)

    def generate_demand(self):
        """
        Invokes for each spatial unit a dedicated process which generates demand
        """
        spawned = self._env.event()

        for unit in self._spatial_units:
            self._world.demand_processes.append(
                self._env.process(self.spawn_demand_process(unit))
            )

        yield spawned.succeed()

    def spawn_demand_process(self, spatial_unit):
        """
        Spawn a demand generator on given spatial unit.
        :param spatial_unit: Identifier of the spatial unit (e.g., hex id)
        :return: None
        """

        # Filter data on spatial unit such that we don't need to filter on the entire demand profile
        local_demand_profile = self._demand_profile[
            (self._demand_profile[self._origin_column] == spatial_unit)
        ]
        # local_demand_profile.loc[:,'o_poisson_est'] /= 4
        # Run until simulation ends
        while DemandFactory.counter < self._maximal_demand:
            try:
                # Transform current time to temporal buckets as defined in the demand profile
                time_bucket = SimulationTimeConverter.convert_to_temporal_bucket(
                    self._time.now(),
                    self._demand_importer._get_temporal_duration_in_hours(),
                )
                non_working_day = SimulationTimeConverter.convert_to_day_of_week_bucket(
                    self._time.now()
                )

                # Filter demand profile on current time
                demand_slice = local_demand_profile[
                    (local_demand_profile[self._temporal_column] == time_bucket)
                    & (
                        local_demand_profile[self._day_of_week_column]
                        == non_working_day
                    )
                ]
                if demand_slice.shape[0] == 0:
                    logging.debug(
                        f"Hex: {spatial_unit}  Time: {time_bucket}  Date:{non_working_day}  Env Time: {self._time.now()}",
                        extra={"clazz": self.__class__.__name__},
                    )
                    # no lambda for given demand slice means there were no arrivals in the sample (lambda was zero)
                    poisson_lambda = 0
                else:
                    # Extract Poisson Estimate for given spatio-temporal cell
                    poisson_lambda = demand_slice.iloc[0]["o_poisson_est"]

                # TODO: to define the target fleet
                random_number = self._rng.random(1)
                if random_number < 0.5:
                    fleet = 0
                else:
                    fleet = 1

                # Based on Poisson Estimate sample next arrival time (in minutes)
                # inter_arrival_time = numpy.random.exponential(
                #    1.0 / poisson_lambda) * self._demand_importer._get_temporal_duration_in_hours() * 60

                if poisson_lambda == 0:
                    # lambda is zero, waiting until next timebucket is reached
                    bucket_in_minutes = (
                        self._demand_importer._get_temporal_duration_in_hours() * 60
                    )
                    time_to_next_bucket = bucket_in_minutes - (
                        self._time.now() % bucket_in_minutes
                    )
                    yield self._env.timeout(time_to_next_bucket)
                    continue
                else:
                    try:
                        if self._modifiers[spatial_unit] == 0:
                            logging.debug(
                                f"Spatial unit {spatial_unit} is removed from demand generation process"
                            )
                            break

                        # TODO: is this a viable way of modifying exponential sampling using the scale factor?
                        # TODO: if we wait for longer than the timebucket is long, we should probably consider no demand (otherwise we spawn this in the next timebucket and skew the real demand distribution)
                        inter_arrival_time = (
                            self._rng.exponential(
                                1.0 / poisson_lambda / self._modifiers[spatial_unit]
                            )
                            * self._demand_importer._get_temporal_duration_in_hours()
                            * 60
                        )
                    except KeyError:
                        # no modifier is registered for that spatial unit
                        inter_arrival_time = (
                            self._rng.exponential(1.0 / poisson_lambda)
                            * self._demand_importer._get_temporal_duration_in_hours()
                            * 60
                        )

                    # await next arrival
                    yield self._env.timeout(inter_arrival_time)

                    # Sample Destination
                    prob_array = demand_slice["od_multinom_p_est"].to_numpy()

                    # TODO: rename - this has nothing to do with low SOC
                    low_soc_vehicle_sample = self._rng.multinomial(
                        1, prob_array
                    )  # No of vehicles to be charged

                    idx = low_soc_vehicle_sample.argmax()

                    destination = demand_slice.iloc[idx][self._destination_column]

                    # Append Arrival to World
                    # create agent or similar consumers
                    logging.debug(
                        f"Demand generated from hexagon {spatial_unit} to {destination}. Fleet {fleet}",
                        extra={"clazz": self.__class__.__name__, "oid": ""},
                    )

                self._world.add_user(self._mode, fleet, spatial_unit, destination)

                # Increase global counter (not thread safe)
                DemandFactory.counter += 1
            except simpy.Interrupt:
                break

    def reset(self):
        # Terminate all ongoing demand processes
        self._world.stop_all_processes()

        # Clear previous demand/user processes
        self._world.demand_processes.clear()
        self._world.user_processes.clear()
        self._world.users.clear()

        # Reset the global counter
        DemandFactory.counter = 0
