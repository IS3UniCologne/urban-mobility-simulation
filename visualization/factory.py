"""Factory for the live visualization.

Stays free of heavy plotting dependencies.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from simulation.helper.exceptions import MissingDependencyError

if TYPE_CHECKING:
    from simulation.simulation import Simulation
    from visualization.visualization_manager import VisualizationManager

VIZ_ENABLED_ENV_VAR = "UMOSIM_VIZ"


def create_visualization(
    simulation: Simulation, *, force: bool = False
) -> VisualizationManager | None:
    """Build a VisualizationManager if enabled, else None.

    Parameters
    ----------
    simulation : Simulation
        Live simulation whose metrics drive the dashboard.
    force : bool, optional
        Always enable, ignoring the CLI/env toggle. Default False.

    Returns
    -------
    VisualizationManager or None
        Unstarted manager when enabled, None when disabled.

    Raises
    ------
    MissingDependencyError
        Visualization specific dependencies are missing.
    """
    if not force and os.environ.get(VIZ_ENABLED_ENV_VAR) != "1":
        return None
    try:
        from visualization.visualization_manager import VisualizationManager
    except ImportError as exc:
        raise MissingDependencyError(
            "Visualization requested (--viz) but dependencies are not installed. "
            "Install the extra: uv sync --extra viz"
        ) from exc
    return VisualizationManager(simulation, interval=10.0)
