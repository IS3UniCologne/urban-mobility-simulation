"""Base class for all ridehailing operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from simulation.operator.operations_management.operations import (
    Operations,
    OperationsDependencies,
)

if TYPE_CHECKING:
    from simulation.helper.configuration.configuration import (
        RideHailingOperationsConfig,
    )


class RideHailingOperations(Operations):
    """Parent class for all ridehailing operations.

    This class extends the generic Operations class with ridehailing-specific functionality.
    """

    # TODO: Move shared logic here

    def __init__(self, deps: OperationsDependencies) -> None:
        super().__init__(deps)

    @property
    def config(self) -> RideHailingOperationsConfig:  # noqa: D102
        return cast("RideHailingOperationsConfig", self._config)
