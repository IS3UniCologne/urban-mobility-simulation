import numpy

from simulation.world.demand.demand_importer import DemandImporter
import logging

from simulation.world.world import World


class DemandFactory:
    counter = 0

    def __init__(self, env, demand_profile, demand_importer: DemandImporter, world: World, maximal_demand = 1_000_000):
        self._env = env
        self._demand_profile = demand_profile
        self._demand_importer = demand_importer
        self._world = world

        origin, destination = demand_importer._get_spatial_column()
        temporal = demand_importer._get_temporal_column()
        day_of_week_column = demand_importer._get_day_of_week_column()

        self._origin_column = origin
        self._destination_column = destination
        self._temporal_column = temporal
        self._day_of_week_column = day_of_week_column

        self._maximal_demand = maximal_demand

        self._spatial_units = list(self._demand_profile[origin].unique())

        # Randon Number Generator
        self._random = numpy.random.RandomState(42)

    def generate_demand(self):
        """
            Invokes for each spatial unit a dedicated process which generates demand
        """
        spawned = self._env.event()

        for unit in self._spatial_units:
            self._env.process(self.spawn_demand_process(unit))

        yield spawned.succeed()

    def spawn_demand_process(self, spatial_unit):
        """
        Spawn a demand generator on given spatial unit.
        :param spatial_unit: Identifier of the spatial unit (e.g., hex id)
        :return: None
        """

        # Filter data on spatial unit such that we don't need to filter on the entire demand profile
        local_demand_profile = self._demand_profile[(self._demand_profile[self._origin_column] == spatial_unit)]

        # Run until simulation ends
        while (DemandFactory.counter < self._maximal_demand):
            # Transform current time to temporal buckets as defined in the demand profile
            time_bucket = self._convert_running_time_to_temporal_bucket(self._env.now)
            non_working_day = self._convert_running_time_to_day_of_week_bucket(self._env.now)

            # Filter demand profile on current time
            demand_slice = local_demand_profile[(local_demand_profile[self._temporal_column] == time_bucket)
                                               & (local_demand_profile[
                                                     self._day_of_week_column] == non_working_day)
                                               ]
            if(demand_slice.shape[0] == 0):
                print(f"Hex: {spatial_unit}  Time: {time_bucket}  Date:{non_working_day}  Env Time: {self._env.now}")


            # Extract Poisson Estimate for given spatio-temporal cell
            poisson_lambda = demand_slice.iloc[0]["o_poisson_est"]

            # Based on Poisson Estimate sample next arrival time (in minutes)
            #inter_arrival_time = numpy.random.exponential(
            #    1.0 / poisson_lambda) * self._demand_importer._get_temporal_duration_in_hours() * 60

            inter_arrival_time = self._random.exponential(
                1.0 / poisson_lambda) * self._demand_importer._get_temporal_duration_in_hours() * 60

            # await next arrival
            yield self._env.timeout(inter_arrival_time)

            # Sample Destination
            prob_array = demand_slice["od_multinom_p_est"].to_numpy()

            low_soc_vehicle_sample = self._random.multinomial(1, prob_array)  # No of vehicles to be charged

            idx = low_soc_vehicle_sample.argmax()

            destination = demand_slice.iloc[idx][self._destination_column]

            # Append Arrival to World
            # create agent or similar consumers
            logging.debug(f'Demand generated from hexagon {spatial_unit} to {destination}.',
                              extra={"clazz": self.__class__.__name__, "oid": ""})

            self._world.add_user(spatial_unit, destination)

            # Increase global counter (not thread safe)
            DemandFactory.counter += 1


    def _convert_running_time_to_temporal_bucket(self, t):
        # TODO: Move to dedicated time class
        return (t % (24*60)) // (self._demand_importer._get_temporal_duration_in_hours() * 60) # Reduce to one day, then get day of week

    def _convert_running_time_to_day_of_week_bucket(self, t):
        # TODO: Move to dedicated time class
        day_of_week =  (t % (24*60*7)) // (24*60) # Reduce to one week, then get day of week

        if day_of_week < 5:
            return False # Non_Working_Day? No => weekday
        else:
            return True  # Non_Working_Day? Yes (i.e., holidays, weekends)