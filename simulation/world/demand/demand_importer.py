from enum import Enum

from pandas import DataFrame


class TemporalBucket(Enum):
    HOURLY_BUCKETS = 0
    TWO_HOURLY_BUCKETS = 1
    FOUR_HOURLY_BUCKETS = 2
    SIX_HOURLY_BUCKETS = 3
    EIGHT_HOURLY_BUCKETS = 4
    TWELVE_HOURLY_BUCKETS = 5

class SpatialResolution(Enum):
    HEX_7 = 0
    HEX_8 = 1
    HEX_9 = 2

class DemandImporter:

    def __init__(self, temporal_resolution: TemporalBucket = TemporalBucket.FOUR_HOURLY_BUCKETS,
                 spatial_resolution: SpatialResolution =  SpatialResolution.HEX_9,
                 day_of_week = False):

        self._temporal_resolution = temporal_resolution
        self._spatial_resolution = spatial_resolution
        self._day_of_week = day_of_week


    @property
    def temporal_resolution(self):
        return self._temporal_resolution

    @property
    def spatial_resolution(self):
        return self._spatial_resolution

    @property
    def consider_day_of_week(self):
        return self._day_of_week

    def generate_demand(self, trip_data: DataFrame):

        hex_start_column, hex_end_column = self._get_spatial_column()
        temporal_column = self._get_temporal_column()
        day_of_week_column = "is_holiday"
        date_column = "date_start"

        ##################################
        #### First Calculate Arrival Times
        ##################################

        # Count Trips in spatio temporal resolution
        tmp_res = trip_data.groupby(
            [date_column, day_of_week_column, temporal_column, hex_start_column]).agg({"id": "count"}).reset_index()

        arrival_times = tmp_res.groupby([day_of_week_column, temporal_column, hex_start_column]).agg({"id": "mean"}).reset_index()

        # Number of potential temporal combinations (day of week, time of day). We need for each combi a distinct lambda.
        number_of_temporal_combinations = len(arrival_times[day_of_week_column].unique()) * len(arrival_times[temporal_column].unique())

        # Consider only hexagons that have data for each temporal data bucket
        hexagon_to_consider = arrival_times.groupby([hex_start_column]).agg({"id": "count"}).reset_index()
        hexagon_to_consider = hexagon_to_consider[hexagon_to_consider["id"] == number_of_temporal_combinations]
        hexagon_to_consider.drop(columns={"id"}, inplace=True)
        hexagon_to_consider = hexagon_to_consider.sort_values(by=[hex_start_column])
        hexagon_to_consider["key"] = 1 # For Cross Join Later

        # Strip out records for which we don't have complete data (hexagons where #data points < number_of_temporal_combinations)
        arrival_times = arrival_times.merge(hexagon_to_consider, on="h3_start_7", how="inner")

        ####################################################################
        #### Second Calculate Destinations Distribution
        ####################################################################

        destination_counts = trip_data.groupby(
            [date_column, day_of_week_column, temporal_column, hex_start_column, hex_end_column]).agg({"id": "count"})

        # Raw Combinations Date, Holiday, Time Bucket
        raw_date = trip_data.groupby([date_column, day_of_week_column]).agg(
            {"id": "count"}).reset_index()
        raw_time = trip_data.groupby([temporal_column]).agg({"id": "count"}).reset_index()

        raw_date["key"] = 1
        raw_time["key"] = 1

        raw_temporal = raw_date.merge(raw_time, on="key")

        # Raw Combinations of Origin and Destination Hexagons
        raw_origin = hexagon_to_consider.copy(deep=True)
        raw_destination = hexagon_to_consider.copy(deep=True)

        raw_origin["key"] = 1
        raw_destination["key"] = 1

        raw_destination.rename(columns={hex_start_column: hex_end_column}, inplace=True)

        raw_spatial = raw_origin.merge(raw_destination, on="key")

        # Join Temporal and Spatial raw blank
        raw_od = raw_temporal.merge(raw_spatial, on="key")
        raw_od.drop(columns={"id_x", "id_y", "key"}, inplace=True)

        # Join raw blank (all feasible) Origin Destination combinations with calculated data
        od = raw_od.merge(destination_counts,
                          on=[date_column, day_of_week_column, temporal_column, hex_start_column, hex_end_column], how="left")

        # Using these origin destination samples, we need to derive a distribution function.
        # That distribution function is a conditional probability: P(destination | day_of_week, time_of_day, origin)
        # In other words: we need to calcuate for each triplet (day_of_week, time_of_day, origin)
        # a distribution function as follows:

        # We estimate a ***Multinomial Distribution*** for origin destination trip generation
        # We need to calculate for each (Day Of Week, Time_Bucket, Origin) a seperate Multinomial Distribution
        # Calculate Daily Trips from Region to Region for each time bucket and weekday
        trips_per_day_per_region = od.groupby([day_of_week_column, temporal_column, hex_start_column, hex_end_column]).agg(
            {"id": "sum"}).reset_index()
        trips_per_day_per_region = trips_per_day_per_region.rename(columns={"id": "total_trips"})

        # Calculate for each (Day Of Week, Time_Bucket, Origin) Sum_k^K n_{k}
        trip_count_overall = trips_per_day_per_region.groupby([day_of_week_column, temporal_column, hex_start_column]).agg(
            {"total_trips": "sum"}).reset_index()
        trip_count_overall.rename(columns={"total_trips": "sum_total_trips"}, inplace=True)

        # Join Counts with Total Sum
        trips_per_day_per_region = trips_per_day_per_region.merge(trip_count_overall,
                                                                  on=[day_of_week_column, temporal_column, hex_start_column],
                                                                  how="inner")

        # Calculate p_i for each destination for each (Day Of Week, Time_Bucket, Origin) triplet
        trips_per_day_per_region["prob"] = trips_per_day_per_region["total_trips"] / trips_per_day_per_region[
            "sum_total_trips"]


        # Merge OD Distribution with Arrival Time Values
        result = trips_per_day_per_region.merge(arrival_times, on = [day_of_week_column, temporal_column, hex_start_column], how = "left")

        result.rename(columns={"prob":"od_multinom_p_est", "id":"o_poisson_est"}, inplace=True)
        result.drop(columns={"key"}, inplace=True)

        """
        # How To Sample from that Distribution for a given Triplet
        # Convert Probabilities to Numpy Array
        sub_set = result[(result["is_holiday"] == False) & (result["time_bucket_4h"] == 0) & (result["h3_start_7"] == "871f18869ffffff")]
        
        prob_array = sub_set["od_multinom_p_est"].to_numpy()
        
        low_soc_vehicle_sample = np.random.multinomial(1, prob_array) # No of vehicles to be charged
        
        
        idx = low_soc_vehicle_sample.argmax()
        
        sub_set.iloc[idx] or sub_set.iloc[idx]["h3_end_7"]
        
        """

        return result



    def _get_spatial_column(self):
        if self.spatial_resolution == SpatialResolution.HEX_7:
            return "h3_start_7", "h3_end_7"
        elif self.spatial_resolution == SpatialResolution.HEX_8:
            return "h3_start_8", "h3_end_8"
        elif self.spatial_resolution == SpatialResolution.HEX_9:
            return "h3_start_9", "h3_end_9"
        else:
            return "h3_start_9", "h3_end_9"


    def _get_temporal_column(self):
        if self.temporal_resolution == TemporalBucket.HOURLY_BUCKETS:
            return "hour_of_day"
        elif self.temporal_resolution == TemporalBucket.TWO_HOURLY_BUCKETS:
            return "time_bucket_2h"
        elif self.temporal_resolution == TemporalBucket.FOUR_HOURLY_BUCKETS:
            return "time_bucket_4h"
        elif self.temporal_resolution == TemporalBucket.SIX_HOURLY_BUCKETS:
            return "time_bucket_6h"
        elif self.temporal_resolution == TemporalBucket.EIGHT_HOURLY_BUCKETS:
            return "time_bucket_8h"
        elif self.temporal_resolution == TemporalBucket.TWELVE_HOURLY_BUCKETS:
            return "time_bucket_12h"
        else:
            return "time_bucket_4h"

    def _get_day_of_week_column(self):
        return "dayofweek"




