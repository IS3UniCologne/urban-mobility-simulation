"""tests for charging price broadcasting and time-weighted charging prices."""

from unittest.mock import Mock

import pytest
import simpy
from pydantic import ValidationError

from simulation.helper.configuration.configuration import ChargingInfrastructureConfig
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)

pytestmark = pytest.mark.unit

LOCATIONS = ["871f18b25ffffff", "871f18865ffffff"]
# distinct price per hour so every lookup is checkable: 0.1, 0.11, ..., 0.33
PROFILE = [round(0.10 + 0.01 * h, 2) for h in range(24)]


# create charging infrastructure configs for tests
def make_config(**overrides: object) -> ChargingInfrastructureConfig:
    defaults = dict(
        NUMBER_OF_CHARGING_STATIONS=len(LOCATIONS),
        LOCATIONS=LOCATIONS,
        CHARGING_STATION_POWER=[50.0],
        CHARGING_STATION_CAPACITY=[20],
        CHARGING_STATION_QUEUE_SIZE=[99],
        CHARGING_STATION_PRICE_PROFILE=PROFILE,
    )
    defaults.update(overrides)

    return ChargingInfrastructureConfig(**defaults)


# create mock simulation for tests
def make_sim(initial_time: float = 0.0) -> Mock:
    sim = Mock()
    sim.env = simpy.Environment(initial_time=initial_time)
    sim.uid_manager.generate_uid.return_value = (1, "uid")
    sim.log_manager.get_uid_logger.return_value = Mock()
    sim.config.world.SPATIAL_RESOLUTION = 7
    return sim


# creates charging infrastructure for tests
def make_infrastructure(
    sim: Mock, profile: list[float] = PROFILE
) -> ChargingInfrastructure:
    return ChargingInfrastructure(
        sim, make_config(CHARGING_STATION_PRICE_PROFILE=profile)
    )


# converts time of day into simulation minutes, e.g. 17.40 = 1060
def hhmm(hours: int, minutes: int = 0) -> float:
    return hours * 60 + minutes


class TestPriceProfileConfig:
    # valid 24h profile should be accepted and kept unchanged
    def test_validprofile_is_kept_unchanged(self) -> None:
        assert make_config().CHARGING_STATION_PRICE_PROFILE == PROFILE

    # invalid profiles should get rejected and error message names the field
    @pytest.mark.parametrize("length", [0, 1, 23, 25])
    def test_profile_with_wrong_length_raises(self, length: int) -> None:
        with pytest.raises(ValidationError, match="CHARGING_STATION_PRICE_PROFILE"):
            make_config(CHARGING_STATION_PRICE_PROFILE=[0.143] * length)

    # config without a profile should be rejected
    def test_missing_profile_raises(self) -> None:
        config = make_config().model_dump(
            exclude={"CHARGING_STATION_PRICE_PROFILE", "instance"}
        )
        with pytest.raises(ValidationError):
            ChargingInfrastructureConfig(**config)


class TestPriceBroadcast:
    # price should be set right at simulation start
    # checks run at h:01, not h:00, to avoid the boundary tie with the broadcast
    def test_price_is_set_at_simulation_start(self) -> None:
        sim = make_sim()
        infra = make_infrastructure(sim)
        sim.env.run(until=1)
        assert all(s.price_per_kWh == PROFILE[0] for s in infra.charging_stations)

    # each hour should have the correctly broadcasted price
    @pytest.mark.parametrize("hour", [1, 5, 17, 23])
    def test_all_stations_get_current_hour_price(self, hour: int) -> None:
        sim = make_sim()
        infra = make_infrastructure(sim)
        sim.env.run(until=hhmm(hour, 1))
        assert all(s.price_per_kWh == PROFILE[hour] for s in infra.charging_stations)

    # after midnight, the price profile should repeat, so 24.30 = 0.30
    def test_profile_repeats_after_midnight(self) -> None:
        sim = make_sim()
        infra = make_infrastructure(sim)
        sim.env.run(until=hhmm(24, 30))
        assert infra.charging_stations[0].price_per_kWh == PROFILE[0]

    # if a simulation begins at 17.41, the price should be set straight away at 17.41 to
    # the price at 17.00 and the next update should be at 18.00, and not at 18.40
    def test_mid_hour_start_broadcasts_immediately_and_on_next_full_hour(self) -> None:
        sim = make_sim(initial_time=hhmm(17, 40))
        infra = make_infrastructure(sim)
        station = infra.charging_stations[0]

        sim.env.run(until=hhmm(17, 41))
        assert station.price_per_kWh == PROFILE[17]

        sim.env.run(until=hhmm(18, 1))
        assert station.price_per_kWh == PROFILE[18]


class TestAveragePrice:
    # give each test a new infrastructure with PROFILE
    @pytest.fixture
    def infra(self) -> ChargingInfrastructure:
        return make_infrastructure(make_sim())

    def test_session_within_one_hour_uses_that_hour(
        self, infra: ChargingInfrastructure
    ) -> None:
        assert infra.average_price(hhmm(17, 19), hhmm(17, 50)) == pytest.approx(
            PROFILE[17]
        )

    def test_session_across_one_boundary(self, infra: ChargingInfrastructure) -> None:
        # 17.40 to 18.50 pays 20 minutes at the 17.00 price and 50 minutes at the 18.00 price
        assert infra.average_price(hhmm(17, 40), hhmm(18, 50)) == pytest.approx(
            (20 * PROFILE[17] + 50 * PROFILE[18]) / 70
        )

    def test_session_across_multiple_boundaries(
        self, infra: ChargingInfrastructure
    ) -> None:
        # 17.40 to 20.15 pays 20 minutes at the 17.00 price, 60 minutes at the 18.00 price, 60 minutes at the 19.00 price, and 15 minutes at the 20.00 price
        assert infra.average_price(hhmm(17, 40), hhmm(20, 15)) == pytest.approx(
            (20 * PROFILE[17] + 60 * PROFILE[18] + 60 * PROFILE[19] + 15 * PROFILE[20])
            / 155
        )

    def test_session_across_midnight(self, infra: ChargingInfrastructure) -> None:
        # 23.40 to 00.50 pays 20 minutes at the 23.00 price and 50 minutes at the 0.00 price
        assert infra.average_price(hhmm(23, 40), hhmm(24, 50)) == pytest.approx(
            (20 * PROFILE[23] + 50 * PROFILE[0]) / 70
        )
