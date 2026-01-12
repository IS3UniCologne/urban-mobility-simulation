"""Fleet metrics module."""

from statistics import mean

from simulation.helper.configuration.enums import PropulsionType, VehicleState
from simulation.helper.types import SimId
from simulation.metrics.metrics_base import IndexedMetricsBase
from simulation.metrics.metrics_dict import MetricsDict
from simulation.operator.vehicle_fleet import VehicleFleet


class FleetMetrics(IndexedMetricsBase):
    """
    Metrics class for fleet-specific metrics.

    Parameters
    ----------
    simulation : Simulation
        Simulation instance providing access to the world and operators.
    """

    def list_available_uids(self) -> list[SimId]:
        """
        Get list of all available fleet IDs.

        Returns
        -------
        list of SimId
            List of fleet unique identifiers.
        """
        return [operator.fleet.uid for operator in self._simulation.world.operators]

    def get_metrics_by_uid(self, uid: SimId) -> MetricsDict:
        """
        Get metrics for a specific fleet by ID.

        Parameters
        ----------
        uid : SimId
            The unique identifier of the fleet.

        Returns
        -------
        MetricsDict
            Metrics dictionary for the specified fleet.

        Raises
        ------
        KeyError
            If the fleet with the given ID is not found.
        """
        fleet = self._get_fleet_by_id(uid)
        if fleet is None:
            raise KeyError(f"Fleet with ID '{uid}' not found")
        return self._get_fleet_metrics(fleet)

    def to_dict(self) -> MetricsDict:
        """
        Return metrics for all fleets.

        Returns
        -------
        MetricsDict
            Mapping of fleet keys to their metrics.
        """
        return MetricsDict(
            {
                f"fleet_{operator.fleet.uid}": self._get_fleet_metrics(operator.fleet)
                for operator in self._simulation.world.operators
            }
        )

    def _get_fleet_by_id(self, fleet_id: str) -> VehicleFleet | None:
        """Find a fleet by its ID."""
        for operator in self._simulation.world.operators:
            if operator.fleet.uid == fleet_id:
                return operator.fleet
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

        # TODO: Not like this, look for similar inefficient code and refactor
        fleet_avg_soc = (
            mean(
                vehicle.energy_system.current_energy_relative
                for vehicle in fleet.vehicles
                if vehicle.propulsion_type not in [PropulsionType.HUMAN_POWERED]
            )
            if fleet.vehicles
            else 0.0
        )

        vehicle_distribution_by_region = fleet.region_vehicle_distribution()

        return MetricsDict(
            {
                "parking_vehicles": parking_vehicles,
                "charging_vehicles": charging_vehicles,
                "driving_vehicles": driving_vehicles,
                "relocating_vehicles": relocating_vehicles,
                "pre_service_vehicles": pre_service_vehicles,
                "moving_to_pick_up_pos_vehicles": moving_to_pick_up_pos_vehicles,
                "avg_state_of_charge": fleet_avg_soc,
                "vehicle_distribution_by_region": vehicle_distribution_by_region,
            }
        )
