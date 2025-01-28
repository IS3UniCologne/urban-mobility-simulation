from configparser import ConfigParser

from simulation.helper.configuration.configuration import (
    AuctionConfig,
    BusConfig,
    ChargingInfrastructureConfig,
    Configuration,
    InfrastructureConfig,
    ModeChoiceConfig,
    PopulationConfig,
    RideHailingOperatorConfig,
    RideHailingVehicleConfig,
    SharedChargingConfig,
    SharedVehicleConfig,
    SharedVehicleOperatorConfig,
    TransitOperatorConfig,
    UserConfig,
)

"""
This module contains the ConfigReader class, which parses the configuration ini file and populates the Configuration singleton with the values.
"""


class ConfigSection:
    """
    A class that represents a ConfigParser Section in the configuration ini file.
    Values are automatically cast to the appropriate type (bool, int, float, list or string) based on their content.
    """

    def __init__(self, parser: ConfigParser, section_name: str):
        self._parser = parser
        self._section_name = section_name
        for option in parser.options(section_name):
            value = parser.get(section_name, option)
            typed_value = self._cast_value(value)
            option_name = option.lower()
            setattr(self, option_name, typed_value)

    def _cast_value(self, value: str):
        """
        Attempts to cast a string value to a boolean, integer, or float.
        If the value contains commas, it is split and each part is cast recursively.
        Returns the original string if no casting is successful.
        """
        for cast_func in (self._str_to_bool, int, float):
            try:
                return cast_func(value)
            except (ValueError, TypeError):
                pass
        if "," in value:
            return [self._cast_value(v.strip()) for v in value.split(",")]
        return value

    def _str_to_bool(self, value: str):
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
        else:
            raise ValueError


class ConfigReader:
    """
    A class that reads the configuration ini file and converts it to a Configuration object.
    """

    def __init__(self, config_file: str):
        self._config_file = config_file
        self._parser = ConfigParser()
        self._global_config = Configuration.instance()

    def load_config(self):
        """
        Reads the configuration file and populates the Configuration singleton.
        """
        if not self._parser.read(self._config_file):
            raise FileNotFoundError(f"Config file '{self._config_file}' not found.")
        self._parse_config_sections()
        self._load_all_configs()

    def _parse_config_sections(self):
        """
        Creates a ConfigSection object for each section in the configuration file.
        """
        if not self._parser.sections():
            raise ValueError("Config file has no valid sections.")

        for section in self._parser.sections():
            setattr(
                self,
                section.lower().replace(":", "_"),
                ConfigSection(parser=self._parser, section_name=section),
            )

    def _load_all_configs(self):
        """
        Calls the appropriate load function for each ConfigSection.
        """
        for section in self._parser.sections():
            if ":" in section:
                prefix, suffix = section.split(":")  # split for vehicle types etc.
                func_name = f"_load_{prefix.lower()}_config"
            else:
                func_name = f"_load_{section.lower()}_config"
                suffix = None
            if not hasattr(self, func_name):
                raise ValueError(
                    f"No load function found for section '{section}' in the ConfigReader."
                )
            if suffix is not None:
                getattr(self, func_name)(
                    suffix
                )  # call function with suffix (e.g. vehicle type)
            else:
                getattr(self, func_name)()

    """
    Everything below this line are section-specific load functions.
    Ideally they should be moved to separate classes in the future.
    """

    def _load_bus_config(self):
        bus_config = BusConfig(
            velocity=self.bus.velocity, max_available_seats=self.bus.seats
        )
        self._global_config.add_bus_config(bus_config)

    def _load_settings_config(self):
        self._global_config.log_level = self.settings.log_level
        self._global_config.file_log_level = self.settings.file_log_level

    def _load_output_config(self):
        self._global_config.set_store_results(self.output.persist_results)
        self._global_config.set_output_path(self.output.output_folder)
        self._global_config.set_transaction_file(self.output.transaction_file)
        self._global_config.set_fleet_state_file(self.output.fleet_state_file)
        self._global_config.track_agent = self.output.track_agent

    def _load_shared_vehicle_operator_config(self):
        recharge_threshold = (self.shared_vehicle_operator.recharge_threshold) / 100.0

        self._global_config.shared_vehicle_population_probabilities = [
            float(self.shared_vehicle_operator.population_probabilities)
        ]  # TODO: is this ever a list ? If not we might want to change how this works.

        charging_station_power = self.shared_vehicle_operator.charging_station_power

        number_of_base_regions = self.shared_vehicle_operator.number_of_base_regions
        base_regions = self.shared_vehicle_operator.base_regions[
            :number_of_base_regions
        ]  # clamp to number of base regions

        number_of_service_workers = (
            self.shared_vehicle_operator.number_of_service_worker
        )

        base_capacity = self.shared_vehicle_operator.base_capacity

        operations_start = self.shared_vehicle_operator.operations_start
        operations_duration = self.shared_vehicle_operator.operations_duration

        vehicle_relocation_velocity = (
            self.shared_vehicle_operator.vehicle_relocation_velocity
        )

        n_cars = self.experiment_management.n_cars
        n_kick_scooters = self.experiment_management.n_kickscooters
        n_bikes = self.experiment_management.n_bikes
        n_scooters = self.experiment_management.n_scooters

        available_modes = (
            self.shared_vehicle_operator.available_vehicle_modes_shared_vehicle
        )

        available_modes_supply = [n_cars, n_scooters, n_kick_scooters, n_bikes]

        svoc = SharedVehicleOperatorConfig(
            recharge_threshold,
            charging_station_power,
            number_of_service_workers,
            base_regions,
            base_capacity,
            operations_start,
            operations_duration,
            vehicle_relocation_velocity,
            available_modes,
            available_modes_supply,
            n_cars,
            n_scooters,
            n_kick_scooters,
            n_bikes,
        )

        self._global_config.add_shared_vehicle_operator_config(svoc)
        return

    def _load_experiment_management_config(self):
        self._global_config.start_time = self.experiment_management.start_time
        self._global_config.end_time = self.experiment_management.end_time
        self._global_config.seed = self.experiment_management.seed

        self

    def _load_demand_config(self):
        self._global_config.trip_demand_file = self.demand.path_trip_demand.format(
            city=self.world.city
        )
        if hasattr(self.demand, "path_demand_modifiers"):
            demand_modifier_files = self.demand.path_demand_modifiers
            if not isinstance(demand_modifier_files, list):
                demand_modifier_files = [demand_modifier_files]
            demand_modifier_files = [
                file.format(city=self.world.city) for file in demand_modifier_files
            ]
            self._global_config.demand_modifier_files = demand_modifier_files

    def _load_world_config(self):
        self._global_config.spatial_resolution = self.world.spatial_resolution
        self._global_config.temporal_resolution = self.world.temporal_resolution
        self._global_config.daily_resolution = self.world.daily_resolution
        self._global_config.city = self.world.city

    def _load_environment_config(self):
        self._global_config.set_bounding_box_file(
            self.environment.path_env_bounding_box.format(city=self.world.city)
        )
        self._global_config.set_env_layer_hex_7_file(
            self.environment.path_env_hex_layer_res_7.format(city=self.world.city)
        )
        self._global_config.set_env_layer_hex_8_file(
            self.environment.path_env_hex_layer_res_8.format(city=self.world.city)
        )
        self._global_config.set_env_layer_hex_9_file(
            self.environment.path_env_hex_layer_res_9.format(city=self.world.city)
        )

    def _load_supply_config(self):
        self._global_config.add_tech_penetration(
            EV_penetration=self.supply.ev_penetration,
            AV_penetration=self.supply.av_penetration,
        )

        if not hasattr(self, "ride_hailing"):
            raise AttributeError(
                "Config file does not contain a section called 'RIDE_HAILING'. "
                "This is required for parsing the 'SUPPLY' section."
            )  ## might make more sense to move RH_availability out of supply instead

        drivers_availability = [
            round(
                float(x)
                * self.ride_hailing.n_ridehailing_cars
                * (1 - self.supply.av_penetration)
            )
            for x in self.supply.rh_availability
        ]

        self._global_config.add_driver_availability_vector(drivers_availability)
        self._global_config.vehicle_supply_file = (
            self.supply.path_vehicle_supply.format(city=self.world.city)
        )

    def _load_mode_choice_model_config(self):
        mc_config = ModeChoiceConfig(
            mode_choice_strategy=self.mode_choice_model.mode_choice_strategy,
            substitution_boundary=self.mode_choice_model.substitution_boundary,
            path_to_model=self.mode_choice_model.path_to_mode_choice_model,
        )
        self._global_config.add_mode_choice_config(mc_config)

    def _load_population_config(self):
        pop_config = PopulationConfig(
            population_probabilities=[
                float(x) for x in self.population.population_probabilities
            ],
            type_paths=self.population.type_paths,
        )
        self._global_config.add_population_config(pop_config)

    def _load_ride_hailing_operator_config(self):
        if not hasattr(self, "ride_hailing"):
            raise AttributeError(
                "Config file does not contain a section called 'RIDE_HAILING'. "
                "This is required for parsing the 'RIDE_HAILING_OPERATOR' section."
            )

        recharge_threshold = [
            float(x) / 100 for x in self.ride_hailing_operator.recharge_threshold
        ]

        rh_operator_config = RideHailingOperatorConfig(
            recharge_threshold=recharge_threshold,
            operations_start=self.ride_hailing_operator.operations_start,
            operations_duration=self.ride_hailing_operator.operations_duration,
            vehicle_relocation_velocity=self.ride_hailing_operator.vehicle_relocation_velocity,
            available_modes=self.ride_hailing.available_vehicle_modes_ridehailing,
            available_modes_supply=[
                self.ride_hailing.n_ridehailing_cars,
                self.ride_hailing.n_autonomous_cars,
            ],
            n_autonomous_cars=self.ride_hailing.n_autonomous_cars,
            n_ridehailing_cars=self.ride_hailing.n_ridehailing_cars,
            allocation=self.ride_hailing.allocation,
            allocation_penalty=self.ride_hailing_operator.low_soc_penalty,
            bid_default=self.ride_hailing_operator.bid_default,
            bid_decay=self.ride_hailing_operator.bid_decay,
            random_overbidding=self.ride_hailing_operator.random_overbidding,
            overbid_prob=self.ride_hailing_operator.overbid_prob,
        )
        self._global_config.add_ridehailing_operator_config(rh_operator_config)

    def _load_ride_hailing_config(self):
        self._global_config.add_tech_penetration(
            self.supply.ev_penetration, self.supply.av_penetration
        )
        self._global_config.add_AV_trust(self.mode_choice_model.av_trust)

        discount_rate = self.ride_hailing.discount_rate

        price_params = [
            float(x) * (1 - discount_rate) for x in self.ride_hailing.price_params
        ]

        self._global_config.add_ride_hailing_info(
            driver_payment_share=self.ride_hailing.driver_payment_share,
            AV_price_reduction=self.ride_hailing.av_price_reduction,
            price_params=price_params,
        )

        self._global_config.ride_hailing_population_probabilities = [
            float(x) for x in self.ride_hailing.population_probabilities
        ]

        self._global_config.add_distance_threshold_to_user(
            self.ride_hailing.max_pickup_distance
        )

    def _load_ride_hailing_vehicle_config(self, vehicle_type: str):
        # concatenate "ride_hailing_vehicle_" with vehicle type to get full section name
        section = getattr(self, f"ride_hailing_vehicle_{vehicle_type.lower()}")

        ride_hailing_vehicle_config = RideHailingVehicleConfig(
            price_per_min=section.price_per_min,
            max_state_of_charge=section.max_state_of_charge,
            energy_consumption=section.energy_consumption,
            velocity=section.velocity,
            max_available_seats=section.max_available_seats,
            initial_SoC=section.initial_soc,
            charging_cost_per_kWh=section.charging_cost_per_kwh,
            cost_per_km=section.cost_per_km,
            daily_total_cost=section.daily_total_cost,
            EV_relative_energy_consumption=section.ev_relative_energy_consumption,
            emergency_soc_buffer=section.emergency_soc_buffer,
        )
        self._global_config.add_ridehailing_vehicle_config(
            vehicle_type_name=vehicle_type,
            ridehailing_vehicle_config=ride_hailing_vehicle_config,
        )

    def _load_shared_vehicle_config(self, vehicle_type: str):
        # concatenate "shared_vehicle_" with vehicle type to get full section name
        section = getattr(self, f"shared_vehicle_{vehicle_type.lower()}")

        shared_vehicle_config = SharedVehicleConfig(
            price_per_min=section.price_per_min,
            max_state_of_charge=section.max_state_of_charge,
            energy_consumption=section.energy_consumption,
            velocity=section.velocity,
            max_available_seats=section.max_available_seats,
            max_walking_distance=section.walking_distance,
            daily_total_cost=section.daily_total_cost,
            initial_SoC=getattr(section, "initial_soc", None),
            EV_relative_energy_consumption=getattr(
                section, "ev_relative_energy_consumption", None
            ),
            cost_per_km=getattr(section, "cost_per_km", None),
            charging_cost_per_kWh=getattr(section, "charging_cost_per_kwh", None),
            co2_per_km=getattr(section, "kg_co2_per_km", None),
        )
        self._global_config.add_shared_vehicle_config(
            vehicle_type_name=vehicle_type, shared_vehicle_config=shared_vehicle_config
        )

    def _load_charging_infrastructure_config(self):
        locations = self.charging_infrastructure.locations[
            : self.charging_infrastructure.number_of_charging_stations
        ]

        power = self.charging_infrastructure.charging_station_power
        capacity = self.charging_infrastructure.charging_station_capacity
        queue_size = self.charging_infrastructure.charging_station_queue_size

        if not isinstance(power, list):
            power = [power] * len(locations)
        if not isinstance(capacity, list):
            capacity = [capacity] * len(locations)
        if not isinstance(queue_size, list):
            queue_size = [queue_size] * len(locations)

        ci_config = ChargingInfrastructureConfig(
            locations=locations, power=power, capacity=capacity, queue_size=queue_size
        )
        self._global_config.add_charging_infrastructure_config(ci_config)

    def _load_infrastructure_config(self):
        path_transit_timetable = self.infrastructure.path_transit_timetable
        path_transit_shapes = self.infrastructure.path_transit_shapes

        infrastructure_config = InfrastructureConfig(
            path_transit_timetable=path_transit_timetable,
            path_transit_shapes=path_transit_shapes,
        )
        self._global_config.add_infrastructure_config(infrastructure_config)

    def _load_user_config(self):
        user_config = UserConfig(
            spatial_strategy=self.user.spatial_strategy,
            max_wait=self.user.transit_max_wait,
            walking_speed=self.user.walking_speed_kph,
        )
        self._global_config.add_user_config(user_config)

    def _load_transit_operator_config(self):
        transit_config = TransitOperatorConfig(
            planning_lookahead=self.transit_operator.transit_lookahead,
            max_busses=self.transit_operator.max_busses,
        )
        self._global_config.add_transit_operator_config(transit_config)

        self._global_config.transit_population_probabilities = (
            self.transit_operator.population_probabilities
        )

    def _load_auction_config(self):
        auction_config = AuctionConfig(
            auction_start=self.auction.auction_start,
            auction_end=self.auction.auction_end,
        )
        self._global_config.auction_config = auction_config

    def _load_shared_charging_auction_config(self):
        shared_charging_config = SharedChargingConfig(
            auction_interval=self.shared_charging_auction.auction_interval,
            timeslot_duration=self.shared_charging_auction.timeslot_duration,
            auction_lookahead=self.shared_charging_auction.auction_lookahead,
        )
        self._global_config.shared_charging_config = shared_charging_config
