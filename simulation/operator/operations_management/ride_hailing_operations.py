"""Base class for all ridehailing operations."""

from __future__ import annotations

from simulation.operator.operations_management.operations import (
    Operations,
    OperationsDependencies,
)


class RideHailingOperations(Operations):
    """Parent class for all ridehailing operations.

    This class extends the generic Operations class with ridehailing-specific functionality.
    """

    # TODO: Move shared logic here

    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps)
