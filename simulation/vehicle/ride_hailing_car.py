import logging
from typing import TYPE_CHECKING, Generator

from simpy import Environment, Event

from simulation.environment.geodesic_position import GeodesicPosition
from simulation.helper.configuration.configuration import Configuration
from simulation.vehicle.ride_hailing_vehicle import RideHailingVehicle
from simulation.vehicle.vehicle import VehicleState

if TYPE_CHECKING:
    from simulation.environment.geodesic_position import GeodesicPosition

# class RideHailingCarState(Enum):
#     INITIALIZED = 0
#     PARKING = 1
#     DRIVING = 2
#     RELOCATING = 3
#     CHARGING = 4
#     PRE_SERVICE = 5
#     SOME_STATE = 1002
#     RESERVED = 1001
#     MOVING_TO_PICK_UP_POS = 1003
#     ONLINE = 6  # When the driver is online
#     OFFLINE = 7  # When the driver is offline


class RideHailingCar(RideHailingVehicle):
    # Shared Care Counter
    ride_hailing_car_id: int = 0
    vehicle_type: str = "ridehailing_car"  # TODO: make explicit that it's a human-driven car

    def __init__(
        self,
        env: Environment,
        position: "GeodesicPosition",
        velocity: float,
        max_available_seats: int=4,
        max_state_of_charge: float=16.7,
        energy_consumption: float=0.152,
        price_per_min: float=0.26,
        is_electric: bool=True,
    ):
        """

        :param env:
        :param position:
        :param max_available_seats: 16.7 kWH as per Smart EQ specification 16.7
        (see e.g.g, https://www.smart.com/de/de/modelle/smart-eq-fortwo-coupe#technische-daten-smart-eq-fortwo-coupe)
        :param max_state_of_charge:
        :param energy_consumption: 15.2 kWh/100km as per Smart EQ specification
        :param velocity:
        """
        super(RideHailingCar, self).__init__(
            env,
            position,
            velocity,
            max_available_seats,
            max_state_of_charge,
            energy_consumption,
            price_per_min,
            is_electric=is_electric,
        )

        # Increment Shared Car ID
        self.car_id: int = RideHailingCar.ride_hailing_car_id
        self._price_per_minute:float = price_per_min
        self._total_earn:float = 0
        self._shift_earn:float = 0
        self._shift_duration:float = 0
        self._offline_duration:float  = 0
        self._shift_start_time:float  = None
        self._shift_end_time:float  = 0
        self._driver_payment_share:float  = (
            Configuration().ride_hailing_global.DRIVER_PAYMENT_SHARE
        )
        self._state: VehicleState = VehicleState.OFFLINE
        self._online_event: Event = self._env.event()
        self._offline_event: Event = self._env.event()
        RideHailingCar.ride_hailing_car_id += 1

        self._emergency_soc_buffer_percent: float = self._config.ride_hailing_vehicles[
            "RideHailingCar"
        ].EMERGENCY_SOC_BUFFER

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

        logging.debug(
            f"RideHailingCar {self.car_id} started its shift at {time}.",
            extra={"clazz": self.__class__.__name__, "oid": self.car_id},
        )

    def update_shift_end_time(self) -> None:
        time = self._env.now
        self._shift_end_time = time

        logging.debug(
            f"RideHailingCar {self.car_id} ended its shift at {time}.",
            extra={"clazz": self.__class__.__name__, "oid": self.car_id},
        )

    def update_shift_duration(self) -> None:
        self._shift_duration = self._env.now - self._shift_start_time

    def update_offline_duration(self) -> None:
        self._offline_duration = self._env.now - self._shift_end_time

    def update_idle_time(self):  # TODO
        pass

    def update_earned_money(self, payment: float) -> None:
        # Notify earned money for a human-driven car
        earn = payment * self._driver_payment_share
        self._total_earn += earn
        self._shift_earn += earn

        logging.debug(
            f"RideHailingCar {self.car_id} earned {self.shift_earn} since he/she started the shift.",
            extra={"clazz": self.__class__.__name__, "oid": self.car_id},
        )

    def get_online(self) -> None:
        self._state = VehicleState.PARKING
        self.update_shift_start_time()
        self._online_event.succeed()
        self._online_event = self._env.event()
        logging.debug(
            f"Driver {self.car_id} gets online.",
            extra={"clazz": self.__class__.__name__, "oid": self.car_id},
        )

    def get_offline(self) -> None:
        self._state = VehicleState.OFFLINE
        self._shift_earn = 0
        self.update_shift_end_time()
        self._offline_event.succeed()
        self._offline_event = self._env.event()
        logging.debug(
            f"Driver {self.car_id} gets offline.",
            extra={"clazz": self.__class__.__name__, "oid": self.car_id},
        )

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
                    if self.state == VehicleState.PARKING:
                        self.get_offline()
                    # if the driver has a task to do we yield until its completion
                    else:
                        logging.debug(
                            f"Driver {self._id} is {self.state} and has a task to do before getting offline.",
                            extra={
                                "clazz": self.__class__.__name__,
                                "oid": self.car_id,
                            },
                        )
                        yield (
                            self._driver_unmounted
                            | self._vehicle_relocation_finished
                            | self._charging_station_plugged_out
                        )
                        self.get_offline()
            # we check driver decisions every one hour
            yield self._env.timeout(15)
