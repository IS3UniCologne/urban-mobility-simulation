"""Run script for this project."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PROJECT_DIR.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulation.helper.configuration.configuration import Configuration
from simulation.simulation import Simulation
from visualization import create_visualization

ALWAYS_VISUALIZE = False


def main() -> None:
    """Prepare and run the simulation."""
    ### --- PRE-RUN SETUP --- ###
    config = Configuration(str(_PROJECT_DIR))

    ### --- RUN --- ###
    simulation = Simulation(config)

    # Enable with `umosim run --viz` or by setting ALWAYS_VISUALIZE to True.
    # Reove any plllots you don't need.
    viz = create_visualization(simulation, force=ALWAYS_VISUALIZE)
    if viz is not None:
        viz.add_plot(viz.world.active_user_processes)
        viz.add_plot(viz.world.total_vehicles)
        viz.add_plot(viz.world.vehicle_state_distribution)
        viz.add_plot(viz.world.wall_time_per_metric_evaluation)
        viz.add_plot(viz.operators.financials)
        viz.add_plot(viz.operators.aggregate_financials)
        viz.add_plot(viz.operators.total_fulfilled_trips)
        viz.add_plot(viz.operators.trip_fulfillment_rate)
        viz.add_plot(viz.operators.total_service_tasks_scheduled)
        viz.add_plot(viz.operators.finished_service_tasks)
        viz.add_plot(viz.fleets.avg_vehicle_soc)
        viz.add_plot(viz.charging_stations.price_per_kWh)
        viz.start()

    simulation.run_simulation()

    ### --- POST-RUN --- ###
    simulation.metrics.user_metrics.to_log()

    if viz is not None:
        # keep the process alive
        viz.block_until_interrupted()


if __name__ == "__main__":
    main()
