from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulation.context.simulation_context import SimulationContext
    from simulation.operator.data_transfer_object.transportation_alternative import (
        TransportationAlternative,
    )

from simulation.operator.data_transfer_object.vehicle_allocation import (
    VehicleAllocation,
)
from simulation.operator.interface.vehicle_allocation_engine_interface import (
    VehicleAllocationEngineInterface,
)


class PublicTransportAllocationEngine(VehicleAllocationEngineInterface):
    __slots__ = ("_env", "_sim", "_vehicles_assigned_to_users")

    def __init__(self, sim: SimulationContext) -> None:
        self._sim = sim
        self._env = sim.env
        self._vehicles_assigned_to_users = self._env.event()

    def request_vehicle_allocation(
        self,
        user,  # noqa: ANN001
        selected_transportation_alternative: TransportationAlternative,
    ) -> VehicleAllocation:
        """
        In case of public transit allocate each request succesfully as long as the vehicle has available seats
        :param user:
        :param selected_transportation_alternative:
        :return:
        """
        selected_vehicle = selected_transportation_alternative.vehicle

        yield self._env.timeout(
            0.01
        )  # TODO: this is just hacking around the expected generator

        if selected_vehicle.available_seats > 0:
            return VehicleAllocation(
                user,
                selected_vehicle,
                selected_transportation_alternative,
                selected_vehicle.position,
                selected_transportation_alternative,
            )
        else:
            return None

    def notify_user_arrival_at_pick_up_position(  # noqa: ANN201
        self, vehicle_assignment: VehicleAllocation
    ):
        pass
