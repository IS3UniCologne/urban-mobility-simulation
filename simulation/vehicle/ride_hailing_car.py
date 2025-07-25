from __future__ import annotations

from typing import TYPE_CHECKING

from simulation.helper.configuration.enums import VehicleState
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle

if TYPE_CHECKING:
    from collections.abc import Generator

    from simpy import Event

    from simulation.context.simulation_context import SimulationContext
    from simulation.environment.position import Position
    from simulation.helper.configuration.configuration import VehicleConfig
    from simulation.operator.vehicle_fleet import VehicleFleet


class RideHailingCar(RideHailingVehicle):
    __slots__ = (
        "_driver_payment_share",
        "_offline_duration",
        "_offline_event",
        "_online_event",
        "_shift_duration",
        "_shift_earn",
        "_shift_end_time",
        "_shift_start_time",
        "_total_earn",
    )

    def __init__(
        self,
        sim: SimulationContext,
        fleet: VehicleFleet,
        position: Position,
        vehicle_config: VehicleConfig,
    ) -> None:
        """

        :param env:
        :param position:
        :param max_available_seats: 16.7 kWH as per Smart EQ specification 16.7
        (see e.g.g, https://www.smart.com/de/de/modelle/smart-eq-fortwo-coupe#technische-daten-smart-eq-fortwo-coupe)
        :param max_state_of_charge:
        :param energy_consumption: 15.2 kWh/100km as per Smart EQ specification
        :param velocity:
        """
        super().__init__(
            sim=sim, fleet=fleet, position=position, vehicle_config=vehicle_config
        )

        self._price_per_minute = vehicle_config.PRICE_PER_MIN
        self._total_earn = 0
        self._shift_earn = 0
        self._shift_duration = 0
        self._offline_duration = 0
        self._shift_start_time = None
        self._shift_end_time = 0
        self._driver_payment_share = (
            self._sim.config.ride_hailing_global.DRIVER_PAYMENT_SHARE
        )
        self.state = VehicleState.OFFLINE
        self._online_event = self._env.event()
        self._offline_event = self._env.event()

        self._emergency_soc_buffer_percent = vehicle_config.EMERGENCY_SOC_BUFFER

        self._env.process(self.run_shift_check_process())

    @property
    def total_earn(self) -> float:
        return self._total_earn

    @property
    def shift_earn(self) -> float:
        return self._shift_earn

    @property
    def shift_duration(self) -> float:
        return self._shift_duration

    @property
    def offline_duration(self) -> float:
        return self._offline_duration

    @property
    def shift_start_time(self) -> float:
        return self._shift_start_time

    @property
    def shift_end_time(self) -> float:
        return self._shift_end_time

    def update_shift_start_time(self) -> None:
        time = self._env.now
        self._shift_start_time = time

        self.logger.debug("Shift has started.")

    def update_shift_end_time(self) -> None:
        time = self._env.now
        self._shift_end_time = time

        self.logger.debug("Shift has ended.")

    def update_shift_duration(self) -> None:
        self._shift_duration = self._env.now - self._shift_start_time

    def update_offline_duration(self) -> None:
        self._offline_duration = self._env.now - self._shift_end_time

    def update_idle_time(self):  # TODO  # noqa: ANN201
        pass

    # TODO do we remove this? If we want this feature it should probably be implemented for all vehicles
    # This can also be inferred from transaction logs
    # def update_earned_money(self, payment):
    #     # Notify earned money for a human-driven car
    #     earn = payment * self._driver_payment_share
    #     self._total_earn += earn
    #     self._shift_earn += earn

    # self.logger.debug(
    #     "RideHailingCar %s earned %s since he/she started the shift.",
    #     self._id,
    #     self.shift_earn,
    #
    # )

    def get_online(self) -> None:
        self.state = VehicleState.PARKING
        self.update_shift_start_time()
        self._online_event.succeed()
        self._online_event = self._env.event()
        self.logger.debug("Driver gets online.")

    def get_offline(self) -> None:
        self.state = VehicleState.OFFLINE
        self._shift_earn = 0
        self.update_shift_end_time()
        self._offline_event.succeed()
        self._offline_event = self._env.event()
        self.logger.debug("Driver gets offline.")

    def decide_to_get_online(self) -> bool:
        go_online = False
        ### comment off when we have mode chioce variables
        # self.update_offline_duration()
        # time = self._env.now
        # week_day = int((time % (24 * 60 * 7)) / (24 * 60))
        # hour = int((time / 60) % 60)
        # offline_duration = self.offline_duration
        # shift_earned = self.shift_earn
        # driver_on_off_model.predict([[0, week_day, hour, offline_duration, shift_earned]])
        # if driver_on_off_model == 1:  # TODO: calibrate the parameters
        #     go_online = True
        fleet_size_threshold = self.fleet.driver_availability_vector()
        time = self._env.now
        hour = int((time % 1440) / 60)
        number_of_online_vehicles = len(self.fleet.get_online_vehicles())
        if number_of_online_vehicles <= fleet_size_threshold[hour]:
            go_online = True
        return go_online

    def decide_to_get_offline(self) -> bool:
        go_offline = False
        ### comment off when we have mode chioce variables
        # self.update_shift_duration()
        # time = self._env.now
        # week_day = int((time % (24 * 60 * 7)) / (24 * 60))
        # hour = int((time / 60) % 60)
        # shift_duration = self.shift_duration
        # shift_earned = self.shift_earn
        # driver_on_off_model.predict([[0, week_day, hour, shift_duration, shift_earned]])
        # if driver_on_off_model == 1:  # TODO: calibrate the parameters
        #     go_offline = True
        fleet_size_threshold = self.fleet.driver_availability_vector()
        time = self._env.now
        hour = int((time % 1440) / 60)
        number_of_online_vehicles = len(self.fleet.get_online_vehicles())
        if number_of_online_vehicles >= fleet_size_threshold[hour]:
            go_offline = True

        return go_offline

    def run_shift_check_process(self) -> Generator[Event, None, None]:
        """
        Run availability decision-making process of drivers
        :return:
        """
        while True:
            # If the driver is offline we check the decision of getting online
            if self.state == VehicleState.OFFLINE:
                go_online = self.decide_to_get_online()
                if go_online:
                    self.get_online()
            # If the driver is online we check the decision of getting offline
            elif self.state in [VehicleState.PARKING]:
                self.update_offline_duration()
                go_offline = self.decide_to_get_offline()
                if go_offline:
                    if (
                        self.state == VehicleState.PARKING
                    ):  # TODO: Why are we checking for parking twice in a row?
                        self.get_offline()
                    # if the driver has a task to do we yield until its completion
                    else:
                        self.logger.debug(
                            "Driver is %s and has a task to do before getting offline.",
                            self.state,
                        )
                        yield (
                            self._driver_unmounted
                            | self._vehicle_relocation_finished
                            | self._charging_station_plugged_out
                        )
                        self.get_offline()
            # we check driver decisions every one hour
            yield self._env.timeout(15)
            yield self._env.timeout(15)
