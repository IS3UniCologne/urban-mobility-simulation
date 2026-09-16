"""Unit tests for the operator cost ledger."""

from unittest.mock import Mock

import pytest

from simulation.helper.configuration.configuration import (
    VehicleCostConfig,
    WorkerCostConfig,
)
from simulation.helper.types import SimId
from simulation.operator.cost_accounting import (
    CostBearingVehicle,
    CostBearingWorker,
    CostLedger,
    CostType,
)

pytestmark = pytest.mark.unit


def make_cost_config(**overrides: float) -> VehicleCostConfig:
    defaults = dict(
        PER_KM=0.5,
        CHARGING_PER_KWH=0.3,
        DAILY=28.8,  # 0.02 per minute
        DRIVER_PAYMENT_SHARE=0.75,
    )
    defaults.update(overrides)
    return VehicleCostConfig(**defaults)


class VehicleStub:
    """Minimal CostBearingVehicle for exercising the ledger without a Vehicle."""

    def __init__(self, uid: str, cost_config: VehicleCostConfig) -> None:
        self._uid = SimId(uid)
        self._cost_config = cost_config

    @property
    def uid(self) -> SimId:
        """Identity the ledger attributes costs to."""
        return self._uid

    @property
    def cost_config(self) -> VehicleCostConfig:
        """Operator cost rates for this vehicle."""
        return self._cost_config


class WorkerStub:
    """Minimal CostBearingWorker for exercising the ledger."""

    def __init__(self, uid: str, cost_config: WorkerCostConfig) -> None:
        self._uid = SimId(uid)
        self._cost_config = cost_config

    @property
    def uid(self) -> SimId:
        """Identity the ledger attributes costs to."""
        return self._uid

    @property
    def cost_config(self) -> WorkerCostConfig:
        """Operator cost rates for this worker."""
        return self._cost_config


def make_vehicle(
    cost_config: VehicleCostConfig, uid: str = "vehicle-1"
) -> CostBearingVehicle:
    return VehicleStub(uid=uid, cost_config=cost_config)


def make_worker(uid: str = "worker-1", hourly: float = 30.0) -> CostBearingWorker:
    return WorkerStub(uid=uid, cost_config=WorkerCostConfig(HOURLY=hourly))


class TestCostLedger:
    @pytest.fixture
    def sim(self) -> Mock:
        sim = Mock()
        sim.env = Mock()
        sim.env.now = 0.0
        return sim

    @pytest.fixture
    def ledger(self, sim: Mock) -> CostLedger:
        return CostLedger(sim)

    def test_distance_cost(self, ledger: CostLedger) -> None:
        vehicle = make_vehicle(make_cost_config())
        ledger.record_distance(vehicle, 4000.0, relocation=False)

        totals = ledger.totals_by_type()
        assert totals[CostType.VEHICLE_DISTANCE] == pytest.approx(2.0)
        assert totals[CostType.VEHICLE_RELOCATION_DISTANCE] == 0.0

    def test_relocation_distance_books_separately(self, ledger: CostLedger) -> None:
        vehicle = make_vehicle(make_cost_config())
        ledger.record_distance(vehicle, 4000.0, relocation=False)
        ledger.record_distance(vehicle, 2000.0, relocation=True)

        totals = ledger.totals_by_type()
        assert totals[CostType.VEHICLE_DISTANCE] == pytest.approx(2.0)
        assert totals[CostType.VEHICLE_RELOCATION_DISTANCE] == pytest.approx(1.0)

    def test_distance_cost_zero_rate(self, ledger: CostLedger) -> None:
        vehicle = make_vehicle(make_cost_config(PER_KM=0.0))
        ledger.record_distance(vehicle, 4000.0, relocation=False)

        assert ledger.totals_by_type()[CostType.VEHICLE_DISTANCE] == 0.0

    def test_charging_cost(self, ledger: CostLedger) -> None:
        vehicle = make_vehicle(make_cost_config())
        ledger.record_energy_charged(vehicle, 10.0)

        assert ledger.totals_by_type()[CostType.VEHICLE_CHARGING] == pytest.approx(3.0)

    def test_charging_cost_zero_rate(self, ledger: CostLedger) -> None:
        vehicle = make_vehicle(make_cost_config(CHARGING_PER_KWH=0.0))
        ledger.record_energy_charged(vehicle, 10.0)

        assert ledger.totals_by_type()[CostType.VEHICLE_CHARGING] == 0.0

    def test_time_accrual_repeated_query_adds_nothing(
        self, sim: Mock, ledger: CostLedger
    ) -> None:
        vehicle = make_vehicle(make_cost_config())
        ledger.register_vehicle(vehicle)

        sim.env.now = 100.0
        first = ledger.totals_by_type()
        second = ledger.totals_by_type()

        assert first == second
        assert first[CostType.VEHICLE_TIME] == pytest.approx(100.0 * 0.02)

    def test_daily_rate_accrues_over_a_full_day(
        self, sim: Mock, ledger: CostLedger
    ) -> None:
        vehicle = make_vehicle(make_cost_config())
        ledger.register_vehicle(vehicle)

        sim.env.now = 1440.0

        assert ledger.totals_by_type()[CostType.VEHICLE_TIME] == pytest.approx(28.8)

    def test_daily_rate_zero_rate(self, sim: Mock, ledger: CostLedger) -> None:
        vehicle = make_vehicle(make_cost_config(DAILY=0.0))
        ledger.register_vehicle(vehicle)

        sim.env.now = 1440.0

        assert ledger.totals_by_type()[CostType.VEHICLE_TIME] == 0.0

    def test_accrual_starts_at_registration(
        self, sim: Mock, ledger: CostLedger
    ) -> None:
        sim.env.now = 500.0
        vehicle = make_vehicle(make_cost_config())
        ledger.register_vehicle(vehicle)

        sim.env.now = 1940.0

        assert ledger.totals_by_type()[CostType.VEHICLE_TIME] == pytest.approx(28.8)

    def test_caller_side_interval_diff(self, sim: Mock, ledger: CostLedger) -> None:
        vehicle = make_vehicle(make_cost_config())
        ledger.register_vehicle(vehicle)
        ledger.record_distance(vehicle, 2000.0, relocation=False)

        sim.env.now = 100.0
        snapshot = ledger.totals_by_type()

        ledger.record_distance(vehicle, 2000.0, relocation=False)
        sim.env.now = 200.0
        current = ledger.totals_by_type()
        delta = {ct: current[ct] - snapshot[ct] for ct in CostType}

        assert delta[CostType.VEHICLE_DISTANCE] == pytest.approx(1.0)
        assert delta[CostType.VEHICLE_TIME] == pytest.approx(100.0 * 0.02)
        assert delta[CostType.VEHICLE_CHARGING] == 0.0

    def test_fare_applies_vehicles_own_share(self, ledger: CostLedger) -> None:
        vehicle = make_vehicle(make_cost_config())
        ledger.report_driver_trip_compensation(vehicle, 10.0)

        assert ledger.totals_by_type()[CostType.DRIVER_PAYMENT] == pytest.approx(7.5)

    def test_fare_zero_share_ignored(self, ledger: CostLedger) -> None:
        vehicle = make_vehicle(make_cost_config(DRIVER_PAYMENT_SHARE=0.0))
        ledger.report_driver_trip_compensation(vehicle, 10.0)

        assert ledger.totals_by_type()[CostType.DRIVER_PAYMENT] == 0.0

    def test_fare_share_is_per_vehicle(self, ledger: CostLedger) -> None:
        human = make_vehicle(make_cost_config(), uid="human")
        autonomous = make_vehicle(
            make_cost_config(DRIVER_PAYMENT_SHARE=0.0), uid="autonomous"
        )
        ledger.report_driver_trip_compensation(human, 10.0)
        ledger.report_driver_trip_compensation(autonomous, 10.0)

        by_entity = ledger.totals_by_entity(CostType.DRIVER_PAYMENT)
        assert by_entity == {SimId("human"): pytest.approx(7.5)}

    def test_worker_time_active_spans_only(self, sim: Mock, ledger: CostLedger) -> None:
        worker = make_worker()
        ledger.register_worker(worker, active=False)

        sim.env.now = 60.0
        ledger.set_worker_active(worker, active=True)

        sim.env.now = 90.0
        ledger.set_worker_active(worker, active=True)

        sim.env.now = 120.0
        ledger.set_worker_active(worker, active=False)

        sim.env.now = 300.0
        # Active from 60 to 120 at 30/h = 0.5/min
        assert ledger.totals_by_type()[CostType.WORKER_TIME] == pytest.approx(30.0)

    def test_worker_zero_rate_accrues_nothing(
        self, sim: Mock, ledger: CostLedger
    ) -> None:
        worker = make_worker(hourly=0.0)
        ledger.register_worker(worker, active=True)

        sim.env.now = 600.0

        assert ledger.totals_by_type()[CostType.WORKER_TIME] == 0.0

    def test_caller_side_interval_diff_per_entity(
        self, sim: Mock, ledger: CostLedger
    ) -> None:
        vehicle_a = make_vehicle(make_cost_config(), uid="vehicle-a")
        vehicle_b = make_vehicle(make_cost_config(), uid="vehicle-b")
        ledger.register_vehicle(vehicle_a)
        ledger.register_vehicle(vehicle_b)

        sim.env.now = 100.0
        snapshot = ledger.totals_by_entity()

        ledger.record_distance(vehicle_a, 2000.0, relocation=False)
        sim.env.now = 200.0
        current = ledger.totals_by_entity()

        # Both accrue 100 min of daily cost; only vehicle-a drove.
        assert current[SimId("vehicle-a")] - snapshot[SimId("vehicle-a")] == (
            pytest.approx(100.0 * 0.02 + 1.0)
        )
        assert current[SimId("vehicle-b")] - snapshot[SimId("vehicle-b")] == (
            pytest.approx(100.0 * 0.02)
        )

    def test_totals_by_entity(self, sim: Mock, ledger: CostLedger) -> None:
        vehicle_a = make_vehicle(make_cost_config(), uid="vehicle-a")
        vehicle_b = make_vehicle(make_cost_config(), uid="vehicle-b")
        ledger.record_distance(vehicle_a, 2000.0, relocation=False)
        ledger.record_distance(vehicle_b, 4000.0, relocation=False)
        ledger.record_energy_charged(vehicle_a, 10.0)

        by_entity = ledger.totals_by_entity(CostType.VEHICLE_DISTANCE)
        assert by_entity == {
            SimId("vehicle-a"): pytest.approx(1.0),
            SimId("vehicle-b"): pytest.approx(2.0),
        }

        all_costs = ledger.totals_by_entity()
        assert all_costs[SimId("vehicle-a")] == pytest.approx(4.0)
        assert all_costs[SimId("vehicle-b")] == pytest.approx(2.0)
