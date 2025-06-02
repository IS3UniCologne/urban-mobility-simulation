from simulation.helper.configuration.configuration import Configuration
from tracking.tracking import Tracking


class DynamicCheckpointRoutingTracker:
    __slots__ = (
        "_agent",
        "_config",
        "_problem",
        "_timestamped_bus_positions",
        "_timestamped_viable_demands",
        "_tracking",
    )

    def __init__(self):  # noqa: ANN204
        self._tracking = Tracking.instance()
        self._config = Configuration()
        self._agent = self._config.dynamic_checkpoint_routing_config.learning_agent
        self._problem = self._config.dynamic_checkpoint_routing_config.problem

        self._timestamped_bus_positions = {}
        self._timestamped_viable_demands = {}

    def track(self):  # noqa: ANN201
        # initialize
        self._log_bus()

        while True:
            yield self._problem._step_executed  # noqa: SLF001
            self._log_bus()

            if self._problem._check_terminal():  # noqa: SLF001
                break

    def _log_bus(self):  # noqa: ANN202
        timestamp = self._problem.bus._time.now_as_str()  # noqa: SLF001

        # ... log bus position ...
        self._timestamped_bus_positions[timestamp] = self._tracking.get(
            self._problem.bus, "position"
        ).getExactLocation(geojson=True)

        # ... log viable demands ...
        self._timestamped_viable_demands[timestamp] = (
            self._problem._get_viable_demands()  # noqa: SLF001
        )

    # # ... build TimeStampedGeoJSON feature ...
    # self._timestamped_bus_positions['geometry']['coordinates'].append(
    #     self._problem.bus.getExactLocation(geojson=True))
    # self._timestamped_bus_positions['properties']['times'].append(
    #     int(self._problem.bus._time.now() * 60000))

    # self._timestamped_position['geometry']['coordinates'].append(init_position.getExactLocation(geojson=True))
    # self._timestamped_position['properties']['times'].append(int(self._time.now() * 60000))
