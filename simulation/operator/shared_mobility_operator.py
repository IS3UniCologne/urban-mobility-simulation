from __future__ import annotations  # noqa: D100

from simulation.helper.configuration.enums import OperatorMode
from simulation.operator.operator import Operator, OperatorDependencies
from simulation.operator.transactions import DemandMonitor


class SharedMobilityOperator(Operator):  # noqa: D101
    __slots__ = ("_demand_monitor", "_number_service_workers", "_workforce")

    def __init__(self, deps: OperatorDependencies) -> None:
        super().__init__(deps=deps)
        self._mode = OperatorMode.SHARED_MOBILITY

    def build_operator_subcomponents(self, deps: OperatorDependencies) -> None:
        """Build subcomponents specific to the shared mobility operator.

        We override this method to add the demand monitor to the transaction log. This is required for
        tracking regional demand for the operations.
        """
        super().build_operator_subcomponents(deps)

        # Register demand monitor to transaction log
        self._demand_monitor: DemandMonitor = DemandMonitor(
            self._fleet.vehicle_types
        )  # TODO: Check if order is correct
        self._transaction_log.add_listener(self._demand_monitor)

    @property
    def demand_monitor(self) -> DemandMonitor:
        """
        Demand monitor for the operator.

        Returns
        -------
        DemandMonitor
            The demand monitor instance.
        """
        return self._demand_monitor
