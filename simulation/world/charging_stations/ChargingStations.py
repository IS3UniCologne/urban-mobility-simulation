from simulation.vehicle.vehicle import VehicleState


class ChargingStationHandler:
    # There is only one instance of this class.
    __instance = None

    @staticmethod
    def instance() -> "ChargingStationHandler":
        """Static access method."""
        if ChargingStationHandler.__instance is None:
            raise Exception("ChargingStationHandler was not initialized")
        else:
            return ChargingStationHandler.__instance

    def __init__(
        self,
        charging_stations_hex_ids: list,
        car_capacity: int,
        scooter_capacity: int,
        kickscooter_capacity: int,
        recharge_threshold: float,
        mixed_fleet,
        env,
        reset: bool = False,
    ):
        self.charging_stations_cars = {
            charging_station_hex_id: 0
            for charging_station_hex_id in charging_stations_hex_ids
        }
        self.charging_stations_scooters = {
            charging_station_hex_id: 0
            for charging_station_hex_id in charging_stations_hex_ids
        }
        self.charging_stations_kickscooters = {
            charging_station_hex_id: 0
            for charging_station_hex_id in charging_stations_hex_ids
        }

        self.car_capacity = car_capacity
        self.scooter_capacity = scooter_capacity
        self.kickscooter_capacity = kickscooter_capacity

        self.recharge_threshold = recharge_threshold

        self.mixed_fleet = mixed_fleet

        self._env = env

        self.charging_stations_hex_ids = charging_stations_hex_ids

        ChargingStationHandler.__instance = self

    def get_car_charging_station_free_capacity(self, hex_id):
        if hex_id in self.charging_stations_hex_ids:
            return self.car_capacity - self.charging_stations_cars[hex_id]
        else:
            return 0

    def get_scooter_charging_station_free_capacity(self, hex_id):
        if hex_id in self.charging_stations_hex_ids:
            return self.scooter_capacity - self.charging_stations_scooters[hex_id]
        else:
            return 0

    def get_kickscooter_charging_station_free_capacity(self, hex_id):
        if hex_id in self.charging_stations_hex_ids:
            return (
                self.kickscooter_capacity - self.charging_stations_kickscooters[hex_id]
            )
        else:
            return 0

    @property
    def env(self):
        return self._env

    @env.setter
    def env(self, env):
        self._env = env

    def try_to_charge(self, vehicle, charging_station_id):
        """
        Here, we check if the charging station is fully occupied. If yes, we do not charge, otherwise, we charge.
        """

        # if no charging station is present, exit
        if (
            charging_station_id not in self.charging_stations_hex_ids
            or not vehicle.state == VehicleState.PARKING
        ):
            # print(f"Vehicle not in charging station or parked. Not able to charge.")
            return

        vehicle.state = VehicleState.PRE_CHARGING
        # get information about the charging station utilization and the capacity for the vehicle type
        charging_station_vehicle, capacity = self.get_charging_station_and_capacity(
            vehicle=vehicle
        )

        # check if sufficient capacity is present
        if charging_station_vehicle[charging_station_id] < capacity:
            # increase capacity

            charging_station_vehicle[charging_station_id] += 1
            # charge vehicle
            # print(f"Charge vehicle in hexagon {charging_station_id} ")
            self.env.process(vehicle.charge())
            self.kpi_tracker.increase_number_of_charging_vehicles(
                self.mixed_fleet.get_vehicle_type(vehicle)
            )
        else:
            # print(f"Tried to charge {self.mixed_fleet.get_vehicle_type(vehicle)} in hexagon {charging_station_id} but failed since charging"
            #      f"station capacity is {capacity}")
            vehicle.state = VehicleState.PARKING

    def decrease_capacity(self, vehicle, charging_station_id):
        charging_station_vehicle, _ = self.get_charging_station_and_capacity(
            vehicle=vehicle
        )
        try:
            charging_station_vehicle[charging_station_id] -= 1
        except Exception:
            pass
        # print(f"Reduce capacity in hexagon {charging_station_id}, to {charging_station_vehicle[charging_station_id]}")

    def search_vehicles_for_charging_and_charge_lowest_soc_vehicle(
        self, vehicle, charging_station_id
    ):
        """
        Here, we search all vehicles within the hexagon 'charging_station_id' based on the vehicle type
        which is given by 'vehicle'. If vehicles are found, we try_to_charge them
        """

        if charging_station_id not in self.charging_stations_hex_ids:
            return

        charging_station_vehicle, capacity = self.get_charging_station_and_capacity(
            vehicle=vehicle
        )

        # only do the checkup if one capacity is left
        if charging_station_vehicle[charging_station_id] == capacity - 1:
            vehicle_type = self.mixed_fleet.get_vehicle_type(vehicle)
            vehicles_below_soc = self.mixed_fleet.get_vehicles_below_soc_level(
                vehicle_type=vehicle_type,
                region=charging_station_id,
                recharge_threshold=self.recharge_threshold,
            )
            # track length of waiting vehicles for charging (in queue)
            self.kpi_tracker.track_maximum_queue_length(
                len(vehicles_below_soc), vehicle_type
            )
            # print(f"Queue length for {vehicle_type}: {len(vehicles_below_soc)}")
            vehicle_with_lowest_soc = None
            lowest_sow = 1

            for vehicle in vehicles_below_soc:
                soc = vehicle.current_relative_state_of_charge
                if soc < lowest_sow:
                    lowest_sow = soc
                    vehicle_with_lowest_soc = vehicle

            if vehicle_with_lowest_soc is not None:
                self.try_to_charge(
                    vehicle=vehicle_with_lowest_soc,
                    charging_station_id=charging_station_id,
                )
                # print(f"charge another vehicle after plugging out vehicle in hexagon {charging_station_id}")

    def get_charging_station_and_capacity(self, vehicle):
        if self.mixed_fleet.get_vehicle_type(vehicle) == "SharedCar":
            return self.charging_stations_cars, self.car_capacity

        elif self.mixed_fleet.get_vehicle_type(vehicle) == "SharedScooter":
            return self.charging_stations_scooters, self.scooter_capacity

        elif self.mixed_fleet.get_vehicle_type(vehicle) == "SharedKickscooter":
            return self.charging_stations_kickscooters, self.kickscooter_capacity
