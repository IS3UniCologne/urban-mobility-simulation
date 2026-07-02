from unittest.mock import Mock

import pytest

from simulation.helper.configuration.configuration import VehicleConfig
from simulation.helper.enums import AutonomyType, PropulsionType, VehicleType
from simulation.vehicle.energy_system.battery_system import BatterySystem
from simulation.vehicle.energy_system.human_powered_system import HumanPoweredSystem
from simulation.vehicle.energy_system.internal_combustion_system import (
    InternalCombustionSystem,
)

pytestmark = pytest.mark.unit


class TestEnergySystem:
    @pytest.fixture
    def sim(self) -> Mock:
        sim = Mock()
        sim.env = Mock()
        sim.uid_manager = Mock()
        sim.uid_manager.generate_uid.return_value = (1, "uid")
        sim.log_manager = Mock()
        sim.log_manager.get_uid_logger.return_value = Mock()
        return sim

    def test_internal_combustion_metrics(self, sim: Mock) -> None:
        # Setup
        vehicle_config = VehicleConfig(
            VELOCITY_KMH=50,
            MAX_AVAILABLE_SEATS=4,
            VEHICLE_TYPE=VehicleType.CAR,
            AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
            PROPULSION_TYPE=PropulsionType.INTERNAL_COMBUSTION,
            ENERGY_CONSUMPTION_PER_KM=0.1,  # per km
            ENERGY_CAPACITY=50.0,
            INITIAL_CHARGE_RATIO=1.0,
            KG_CO2_PER_KM=0.15,
            PRICE_PER_TRIP=0,
        )

        ice = InternalCombustionSystem(sim, vehicle_config)

        # Action 1
        distance1 = 10000.0  # 10 km
        consumed1 = ice.consume_for_distance(distance1)

        # Assert 1
        expected_energy1 = vehicle_config.ENERGY_CONSUMPTION_PER_KM * distance1 / 1000
        assert consumed1 == pytest.approx(expected_energy1)
        assert ice.lifetime_energy_consumed == pytest.approx(expected_energy1)

        expected_emissions1 = (distance1 / 1000) * vehicle_config.KG_CO2_PER_KM
        assert ice.lifetime_emissions == pytest.approx(expected_emissions1)

        # Action 2
        distance2 = 5000.0  # 5 km
        consumed2 = ice.consume_for_distance(distance2)

        # Assert 2
        expected_energy2 = vehicle_config.ENERGY_CONSUMPTION_PER_KM * distance2 / 1000
        assert consumed2 == pytest.approx(expected_energy2)

        # Lifetime should be sum of both
        assert ice.lifetime_energy_consumed == pytest.approx(
            expected_energy1 + expected_energy2
        )

        expected_emissions2 = (distance2 / 1000) * vehicle_config.KG_CO2_PER_KM
        assert ice.lifetime_emissions == pytest.approx(
            expected_emissions1 + expected_emissions2
        )

    def test_battery_electric_metrics(self, sim: Mock) -> None:
        # Setup
        ev_config = VehicleConfig(
            VELOCITY_KMH=50,
            MAX_AVAILABLE_SEATS=4,
            VEHICLE_TYPE=VehicleType.CAR,
            AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
            PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
            ENERGY_CONSUMPTION_PER_KM=0.2,
            ENERGY_CAPACITY=100.0,
            INITIAL_CHARGE_RATIO=1.0,
            KG_CO2_PER_KM=0.05,  # Grid mix
            PRICE_PER_TRIP=0,
        )
        ev = BatterySystem(sim, ev_config)

        # Action 1
        distance1 = 20000.0  # 20 km
        consumed1 = ev.consume_for_distance(distance1)

        # Assert 1
        # Energy consumption: 0.2 * 20000 / 1000 = 4.0
        assert consumed1 == pytest.approx(4.0)
        assert ev.lifetime_energy_consumed == pytest.approx(4.0)

        expected_emissions1 = (distance1 / 1000) * ev_config.KG_CO2_PER_KM
        assert ev.lifetime_emissions == pytest.approx(expected_emissions1)

        # Action 2
        distance2 = 10000.0  # 10 km
        consumed2 = ev.consume_for_distance(distance2)

        # Assert 2
        # Energy consumption: 0.2 * 10000 / 1000 = 2.0
        assert consumed2 == pytest.approx(2.0)

        # Lifetime should be sum of both: 4.0 + 2.0 = 6.0
        assert ev.lifetime_energy_consumed == pytest.approx(6.0)

        expected_emissions2 = (distance2 / 1000) * ev_config.KG_CO2_PER_KM
        assert ev.lifetime_emissions == pytest.approx(
            expected_emissions1 + expected_emissions2
        )

    def test_human_powered_metrics(self, sim: Mock) -> None:
        # Setup
        config = VehicleConfig(
            VELOCITY_KMH=15,
            MAX_AVAILABLE_SEATS=1,
            VEHICLE_TYPE=VehicleType.BIKE,
            AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
            PROPULSION_TYPE=PropulsionType.HUMAN_POWERED,
            ENERGY_CONSUMPTION_PER_KM=0.0,
            ENERGY_CAPACITY=100.0,
            INITIAL_CHARGE_RATIO=1.0,
            KG_CO2_PER_KM=0.0,
            PRICE_PER_TRIP=0,
        )
        human = HumanPoweredSystem(sim, config)

        # Action 1
        distance1 = 5000.0  # 5 km
        consumed1 = human.consume_for_distance(distance1)

        # Assert 1
        assert consumed1 == 0.0
        assert human.lifetime_energy_consumed == 0.0

        expected_emissions1 = (distance1 / 1000) * config.KG_CO2_PER_KM
        assert human.lifetime_emissions == pytest.approx(expected_emissions1)

        # Action 2
        distance2 = 2000.0  # 2 km
        consumed2 = human.consume_for_distance(distance2)

        # Assert 2
        assert consumed2 == 0.0
        assert human.lifetime_energy_consumed == 0.0

        expected_emissions2 = (distance2 / 1000) * config.KG_CO2_PER_KM
        assert human.lifetime_emissions == pytest.approx(
            expected_emissions1 + expected_emissions2
        )

    def test_energy_checks_and_refill(self, sim: Mock) -> None:
        # Setup
        capacity = 100.0
        consumption = 0.2  # per km
        buffer_percent = 0.1  # 10% -> 10.0 units

        ev_config = VehicleConfig(
            VELOCITY_KMH=50,
            MAX_AVAILABLE_SEATS=4,
            VEHICLE_TYPE=VehicleType.CAR,
            AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
            PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
            ENERGY_CONSUMPTION_PER_KM=consumption,
            ENERGY_CAPACITY=capacity,
            INITIAL_CHARGE_RATIO=0.5,  # 50.0 units
            ENERGY_RESERVE_RATIO=buffer_percent,
            KG_CO2_PER_KM=0.0,
            PRICE_PER_TRIP=0,
        )
        ev = BatterySystem(sim, ev_config)

        # Initial state: 50.0 units. Default buffer: 10.0 units. Usable: 40.0 units.

        # 1. Test has_enough_energy with default buffer
        # Distance 100km -> 20.0 units. 50 - 10 >= 20 -> True
        assert ev.has_enough_energy(100000.0) is True

        # Distance 200km -> 40.0 units. 50 - 10 >= 40 -> True (Exact boundary)
        assert ev.has_enough_energy(200000.0) is True

        # Distance 201km -> 40.2 units. 50 - 10 >= 40.2 -> False
        assert ev.has_enough_energy(201000.0) is False

        # 2. Test without reserve buffer
        # No buffer: 50 >= 40.2 -> True
        assert ev.has_enough_energy(201000.0, use_buffer=False) is True

        # No buffer: 50 >= 50 -> True (exact boundary at 250km)
        assert ev.has_enough_energy(250000.0, use_buffer=False) is True

        # No buffer: 50 >= 50.2 -> False (just over capacity at 251km)
        assert ev.has_enough_energy(251000.0, use_buffer=False) is False

        # 3. Test Refill
        # Current: 50.0. Capacity: 100.0.

        # Refill 20 units
        gen = ev.refill(20.0, 300)  # 5 mins
        # It yields a timeout
        next(gen)
        sim.env.timeout.assert_called_with(300)

        # Resume generator to execute post-yield code
        try:
            next(gen)
        except StopIteration:
            pass

        # Check energy updated
        assert ev.current_energy_absolute == pytest.approx(70.0)

        # Refill to full (amount <= 0 or large amount)
        # Let's try large amount first to test capping
        gen = ev.refill(50.0, 300)
        next(gen)
        try:
            next(gen)
        except StopIteration:
            pass
        assert ev.current_energy_absolute == pytest.approx(100.0)

        # Consume some to test refill(0) -> fill up
        ev.consume_for_distance(100000.0)  # -20 units -> 80.0
        assert ev.current_energy_absolute == pytest.approx(80.0)

        gen = ev.refill(0.0, 600)
        next(gen)
        try:
            next(gen)
        except StopIteration:
            pass
        assert ev.current_energy_absolute == pytest.approx(100.0)

    def test_human_powered_checks(self, sim: Mock) -> None:
        config = VehicleConfig(
            VELOCITY_KMH=15,
            MAX_AVAILABLE_SEATS=1,
            VEHICLE_TYPE=VehicleType.BIKE,
            AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
            PROPULSION_TYPE=PropulsionType.HUMAN_POWERED,
            ENERGY_CONSUMPTION_PER_KM=0.0,
            ENERGY_CAPACITY=100.0,
            INITIAL_CHARGE_RATIO=1.0,
            KG_CO2_PER_KM=0.0,
            PRICE_PER_TRIP=0,
        )
        human = HumanPoweredSystem(sim, config)

        assert human.has_enough_energy(1000000.0) is True

        gen = human.refill(10.0, 10)
        next(gen)
        # Should be no-op or just yield timeout(0)
        sim.env.timeout.assert_called_with(0)

    def test_should_use_predicted_energy_when_prediction_set(self, sim: Mock) -> None:
        ev_config = VehicleConfig(
            VELOCITY_KMH=50,
            MAX_AVAILABLE_SEATS=4,
            VEHICLE_TYPE=VehicleType.CAR,
            AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
            PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
            ENERGY_CONSUMPTION_PER_KM=0.2,
            ENERGY_CAPACITY=100.0,
            INITIAL_CHARGE_RATIO=1.0,  # 100.0 units
            ENERGY_RESERVE_RATIO=0.1,  # 10.0 units buffer
            KG_CO2_PER_KM=0.0,
            PRICE_PER_TRIP=0,
        )
        ev = BatterySystem(sim, ev_config)

        # Without prediction: current=100, buffer=10, usable=90
        # 400km -> 80 units required. 100 - 10 >= 80 -> True
        assert ev.has_enough_energy(400000.0) is True

        # Set predicted energy to 30.0 (vehicle mid-session, will have 30 after)
        ev.predicted_energy = 30.0

        # With prediction: predicted=30, buffer=10, usable=20
        # 100km -> 20 units. 30 - 10 >= 20 -> True
        assert ev.has_enough_energy(100000.0) is True

        # 101km -> 20.2 units. 30 - 10 >= 20.2 -> False
        assert ev.has_enough_energy(101000.0) is False

        # 400km -> 80 units. 30 - 10 >= 80 -> False (would pass with current energy)
        assert ev.has_enough_energy(400000.0) is False

        # Without reserve also uses predicted: 30 >= 20.2 -> True
        assert ev.has_enough_energy(101000.0, use_buffer=False) is True

        # Without reserve: 30 >= 60.2 -> False
        assert ev.has_enough_energy(301000.0, use_buffer=False) is False

        # Clear prediction, falls back to current energy
        ev.clear_predicted_energy()
        assert ev.has_enough_energy(400000.0) is True

    def test_calculate_energy_required(self, sim: Mock) -> None:
        # Setup
        config = VehicleConfig(
            VELOCITY_KMH=50,
            MAX_AVAILABLE_SEATS=4,
            VEHICLE_TYPE=VehicleType.CAR,
            AUTONOMY_TYPE=AutonomyType.HUMAN_DRIVEN,
            PROPULSION_TYPE=PropulsionType.BATTERY_ELECTRIC,
            ENERGY_CONSUMPTION_PER_KM=0.2,
            ENERGY_CAPACITY=100.0,
            INITIAL_CHARGE_RATIO=1.0,
            KG_CO2_PER_KM=0.0,
            PRICE_PER_TRIP=0,
        )
        ev = BatterySystem(sim, config)

        # Test calculation
        distance = 10000.0  # 10 km
        expected = 0.2 * 10000.0 / 1000
        assert ev.calculate_energy_required(distance) == pytest.approx(expected)

        # Test with 0 distance
        assert ev.calculate_energy_required(0.0) == 0.0
