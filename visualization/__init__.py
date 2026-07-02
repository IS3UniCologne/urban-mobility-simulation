"""Live visualization package.

Heavy plotting dependencies are only imported once ``VisualizationManager`` is constructed.
"""

from visualization.factory import VIZ_ENABLED_ENV_VAR, create_visualization

__all__ = ["VIZ_ENABLED_ENV_VAR", "create_visualization"]
