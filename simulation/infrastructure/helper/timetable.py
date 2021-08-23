import logging
import geopandas as gpd
import pandas as pd
import datetime

from simulation.helper.time import SimulationTime


class AmbiguousTripException(Exception):
    pass


class Timetable:
    def __init__(self, data_path):
        self._data_path = data_path
        self._trips = None

    @property
    def trips(self):
        return self._trips

    def trip_by_id(self, trip_id):
        trip = self._trips[self._trips['trip_id'] == trip_id]
        trip = trip.sort_values(by='stop_sequence')

        # quick sanity check
        if len(trip[trip.duplicated(subset=['trip_id', 'stop_sequence'])].index) > 0:
            raise AmbiguousTripException(f'Trip ID {trip_id} has ambiguous stop sequence.')

        return trip

    def import_timetable(self):
        logging.debug('Importing GTFS data...',
                      extra={"clazz": self.__class__.__name__, "oid": ""})

        try:
            self._trips = pd.read_csv(self._data_path)
        except FileNotFoundError:
            logging.error(f'{self._data_path} does not exist, use Prepare_Transit_Data notebook to generate first.',
                          extra={"clazz": self.__class__.__name__, "oid": ""})

        self._trips = gpd.GeoDataFrame(self._trips, geometry=gpd.points_from_xy(self._trips['stop_lon'],
                                                                                self._trips['stop_lat']))
        self._trips.sort_values(by=['trip_id', 'stop_sequence'], inplace=True)

    def next_trips(self, time: SimulationTime):

        # look ahead one minute, simulation time is in minutes
        # yield all trips that start (on this weekday) within the next minute
        weekday = time.dayofweek_as_str()
        if time.minutes() == 59:
            if time.hours() == 23:
                weekday = time.next_dayofweek_as_str()
                lookahead = datetime.time(0, 0).strftime('%H:%M:%S')
            else:
                lookahead = datetime.time(time.hours()+1, 0).strftime('%H:%M:%S')
        else:
            lookahead = datetime.time(time.hours(), time.minutes()+1).strftime('%H:%M:%S')
        # TODO what about next day departures - shouldnt be a problem with stop_sequence = 0?

        trips = self._trips.loc[(self._trips[weekday] == 1) &
                                (self._trips['stop_sequence'] == 0) &
                                (self._trips['departure_time'] > time.now_as_str()) &
                                (self._trips['departure_time'] <= lookahead), 'trip_id'].tolist()

        return trips
