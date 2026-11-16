"""GTFS timetable import and trip lookup utilities."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import geopandas as gpd
import pandas as pd

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.exceptions import (
    AmbiguousTripException,
    TimetableNotImportedError,
)
from simulation.helper.simulation_base import SimulationBase
from simulation.helper.time import SimulationTime, SimulationTimeConverter
from simulation.helper.types import GtfsTripId

if TYPE_CHECKING:
    from pathlib import Path

    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.data_transfer_object.transport_request import (
        TransportRequest,
    )


class Timetable(SimulationBase):
    """GTFS timetable holding trip and stop schedules.

    Parameters
    ----------
    data_path : pathlib.Path
        Path to the prepared GTFS trips CSV.
    sim : SimulationContext
        Simulation context.
    """

    __slots__ = ("_data_path", "_geo_env", "_sim", "_trips")

    def __init__(self, data_path: Path, sim: SimulationContext) -> None:
        super().__init__(sim)
        self._data_path = data_path
        self._trips: gpd.GeoDataFrame | None = None
        self._geo_env = sim.geo_env
        self._sim = sim

    @property
    def trips(self) -> gpd.GeoDataFrame:
        """Imported trips frame.

        Raises
        ------
        TimetableNotImportedError
            If accessed before import_timetable has run.
        """
        if self._trips is None:
            raise TimetableNotImportedError(
                "Timetable accessed before import_timetable() was called."
            )
        return self._trips

    def trip_by_id(self, trip_id: GtfsTripId) -> pd.DataFrame:  # noqa: D102
        trips = self.trips
        trip = trips[trips["trip_id"] == trip_id]
        trip = trip.sort_values(by="stop_sequence")

        # quick sanity check
        if len(trip[trip.duplicated(subset=["trip_id", "stop_sequence"])].index) > 0:
            raise AmbiguousTripException(
                f"Trip ID {trip_id} has ambiguous stop sequence."
            )

        return trip

    def import_timetable(self) -> None:  # noqa: D102
        self.logger.debug("Importing GTFS data...")

        try:
            raw_trips = pd.read_csv(self._data_path)
        except FileNotFoundError:
            self.logger.error(
                "%s does not exist, generate the transit data first.", self._data_path
            )
            raise

        trips = gpd.GeoDataFrame(
            raw_trips,
            geometry=gpd.points_from_xy(raw_trips["stop_lon"], raw_trips["stop_lat"]),
        )
        trips = trips.sort_values(by=["trip_id", "stop_sequence"])
        self._trips = trips

    def next_trips(self, time: SimulationTime, lookahead: int) -> list[GtfsTripId]:
        """Return trips departing within the next `lookahead` minutes.

        Parameters
        ----------
        time : SimulationTime
            Current simulation time.
        lookahead : int
            Minutes to look ahead.

        Returns
        -------
        list[GtfsTripId]
            List of trip IDs departing within the lookahead window.
        """
        trips = self.trips
        weekday = time.dayofweek_as_str()
        last_weekday = time.last_dayofweek_as_str()
        if time.minutes() + lookahead > 59:
            if time.hours() == 23:
                last_weekday = weekday
                weekday = time.next_dayofweek_as_str()
                lookahead_strf = datetime.time(0, lookahead - 1).strftime("%H:%M:%S")
            else:
                lookahead_strf = datetime.time(
                    time.hours() + 1, lookahead - 1
                ).strftime("%H:%M:%S")
        else:
            lookahead_strf = datetime.time(
                time.hours(), time.minutes() + lookahead
            ).strftime("%H:%M:%S")

        next_trips = trips.loc[
            (
                ((trips[weekday] == 1) & (~trips["dep_next_day"]))
                | ((trips[last_weekday] == 1) & (trips["dep_next_day"]))
            )
            & (trips["stop_sequence"] == 0)
            & (trips["departure_time"] > time.now_as_str())
            & (trips["departure_time"] <= lookahead_strf),
            "trip_id",
        ].tolist()

        return [GtfsTripId(t) for t in next_trips]

    def find_viable_trips(
        self,
        transport_task: TransportRequest,
        spatial_strategy: str = "hexagon",
        temporal_lookahead: int = 10,
    ) -> gpd.GeoDataFrame:
        """Find viable public transit trips for a search task.

        Parameters
        ----------
        transport_task : TransportRequest
            Request that generated the search.
        spatial_strategy : str
            Strategy for matching stops to the task origin (e.g. "hexagon").
        temporal_lookahead : int
            Minutes into the future for the latest possible departure
            (does not account for walking time).

        Returns
        -------
        geopandas.GeoDataFrame
            Trips reachable on foot and departing within the lookahead window.
        """
        trips = self.trips
        search_time = transport_task.creation_time
        latest_departure = SimulationTimeConverter.as_str(
            search_time + temporal_lookahead
        )
        weekday = SimulationTimeConverter.dayofweek_as_str(search_time)

        # only look at trips that are in service today
        viable_trips = trips[(trips[weekday] == 1)]  # TODO: edge cases?

        # find viable stops in vicinity given a strategy, e.g. hexagon, euclidean distance, walking distance (street network), ...
        viable_trips = self._find_viable_stops(
            viable_trips, spatial_strategy, transport_task.origin
        )

        # calc walk distance and duration
        if spatial_strategy not in ["euclidean", "walk"]:
            # if stops in vicinity were found by hexagon, no distance has been calculated, use euclidean
            viable_trips["walk_dist"] = viable_trips.apply(
                lambda x: (
                    transport_task.origin
                    >> GeodesicPosition(self._sim, x["stop_lat"], x["stop_lon"])
                ),
                axis=1,
            )
        viable_trips["walk_duration"] = viable_trips["walk_dist"] / 83.33

        # find all trips which stops are reachable within the specified temporal_lookahead and depart after arrival by foot
        viable_trips = viable_trips[
            (viable_trips["departure_time"] <= latest_departure)
            & (
                viable_trips.apply(
                    lambda x: SimulationTimeConverter.as_str(
                        search_time + x["walk_duration"]
                    ),
                    axis=1,
                )
                <= viable_trips["departure_time"]
            )
        ]

        # of all those, find trips that have at least one stop in vicinity of the transport task destination
        list(viable_trips["trip_id"].unique())

        return viable_trips

    def _find_viable_stops(
        self, trips: gpd.GeoDataFrame, strategy: str, position: GeodesicPosition
    ) -> gpd.GeoDataFrame:
        if strategy == "hexagon":
            # trips are viable that start/end in the same hexagon
            poly = self._geo_env.get_hexagon(position.get_region_id())
            return trips[trips.within(poly)]
        else:
            raise NotImplementedError(
                "Other strategies for aligning travel demands are not implemented."
            )
