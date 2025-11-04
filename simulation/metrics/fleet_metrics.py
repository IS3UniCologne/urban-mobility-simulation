"""Fleet metrics module."""

from simulation.helper.configuration.enums import VehicleState
from simulation.helper.types import SimId
from simulation.metrics.metrics_base import IndexedMetricsBase
from simulation.metrics.metrics_dict import MetricsDict
from simulation.operator.vehicle_fleet import VehicleFleet


class FleetMetrics(IndexedMetricsBase):
    """Metrics class for fleet-specific metrics."""

    def list_available_uids(self) -> list[str]:
        """Get list of all available fleet IDs."""
        return [fleet.uid for fleet in self._simulation.world.fleets]

    def get_metrics_by_uid(self, uid: SimId) -> MetricsDict:
        """Get metrics for a specific fleet by ID."""
        fleet = self._get_fleet_by_id(uid)
        if fleet is None:
            raise KeyError(f"Fleet with ID '{uid}' not found")
        return self._get_fleet_metrics(fleet)

    def to_dict(self) -> MetricsDict:
        """Return metrics for all fleets."""
        return MetricsDict(
            {
                f"fleet_{fleet.uid}": self._get_fleet_metrics(fleet)
                for fleet in self._simulation.world.fleets
            }
        )

    def _get_fleet_by_id(self, fleet_id: str) -> VehicleFleet | None:
        """Find a fleet by its ID."""
        for fleet in self._simulation.world.fleets:
            if fleet.uid == fleet_id:
                return fleet
        return None

    def _get_fleet_metrics(self, fleet: VehicleFleet) -> MetricsDict:
        """Get metrics for a single fleet."""
        parking_vehicles = len(fleet.vehicles_by_state[VehicleState.PARKING])
        charging_vehicles = len(fleet.vehicles_by_state[VehicleState.CHARGING])
        driving_vehicles = len(fleet.vehicles_by_state[VehicleState.DRIVING])
        relocating_vehicles = len(fleet.vehicles_by_state[VehicleState.RELOCATING])
        pre_service_vehicles = len(fleet.vehicles_by_state[VehicleState.PRE_SERVICE])
        moving_to_pick_up_pos_vehicles = len(
            fleet.vehicles_by_state[VehicleState.MOVING_TO_PICK_UP_POS]
        )
        reserved_vehicles = len(fleet.vehicles_by_state[VehicleState.RESERVED])

        # fleet_avg_soc = mean(vehicle.state_of_charge for vehicle in fleet.vehicles)

        # # TODO: Make this work for all fleet types
        # if fleet.__class__.__name__ == "RideHailingFleet":
        #     current_charge_threshold = fleet.charge_threshold
        #     low_soc_vehicles = [
        #         vehicle
        #         for vehicle in fleet.vehicles
        #         if vehicle.state_of_charge < current_charge_threshold
        #     ]
        # else:
        #     raise NotImplementedError()

        return MetricsDict(
            {
                "parking_vehicles": parking_vehicles,
                "charging_vehicles": charging_vehicles,
                "driving_vehicles": driving_vehicles,
                "relocating_vehicles": relocating_vehicles,
                "pre_service_vehicles": pre_service_vehicles,
                "moving_to_pick_up_pos_vehicles": moving_to_pick_up_pos_vehicles,
                "reserved_vehicles": reserved_vehicles,
            }
        )
