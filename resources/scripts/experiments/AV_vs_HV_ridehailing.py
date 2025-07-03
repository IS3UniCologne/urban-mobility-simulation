# from pqdm.processes import pqdm
import logging
from pathlib import Path

import pandas as pd
import simpy

import utils
from simulation.agent.user import (
    User,  # must come before DemandFactory, otherwise circular imports
)
from simulation.environment.geodesic_environment import GeodesicEnvironment
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.configuration.enums import ModeChoiceStrategy
from simulation.helper.logging.log_manager import LogManager
from simulation.infrastructure.charging_stations.charging_infastructure import (
    ChargingInfrastructure,
)
from simulation.infrastructure.helper.distance_matrix_importer import (
    DistanceMatrixImporter,
)
from simulation.operator.fleet_factory import (
    generate_mixed_ride_hailing_fleet,
    generate_ridehailing_fleet_config,
)
from simulation.operator.operations_management.ridehailing_base_charging_operations import (
    RideHailingBaseChargingOperations,
)
from simulation.operator.ride_hailing_allocation_engine import (
    RideHailingAllocationEngine,
)
from simulation.operator.ride_hailing_operator import RideHailingOperator
from simulation.operator.ride_hailing_search_engine import RideHailingSearchEngine
from simulation.vehicle.ride_hailing_AV import RideHailingAV
from simulation.vehicle.ride_hailing_car import RideHailingCar
from simulation.vehicle_choice_model.only_car_vehicle_choice_behavior import (
    OnlyCarVehicleChoiceBehavior,
)
from simulation.world.demand.demand_factory import DemandFactory
from simulation.world.population.PopulationFactory import PopulationFactory
from simulation.world.world import World
from tracking.tracking import Tracking

pd.set_option("display.max_columns", None)

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Configuration from ini file.       #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #


# Change working directory to path of main.py
# working_dir = Path(__file__).parent
# os.chdir(working_dir)

# Initialize Configuration
config = Configuration()

# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Setup Simulation Environment.           #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Init. Simulation Environment
env = simpy.Environment(initial_time=config.experiment_management.START_TIME)

LogManager.setup_logging(config, env)


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Underlying Spatial Environment.    #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

# Load Spatial Environment
utils.load_geodesic_environment()
# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Load Distance Matrix (once).            #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

geodesic_environment = GeodesicEnvironment.getInstance()
hexagons = geodesic_environment.getLayer(
    f"hex_{config.world.SPATIAL_RESOLUTION_VALUE}"
).index.tolist()
dmi = DistanceMatrixImporter(
    hexagons,
    config.world.SPATIAL_RESOLUTION_VALUE,
    "./data/infrastructure",
    config.world.CITY,
)
distance_matrix = dmi.load_distance_matrix()


def run_single_simulation(  # noqa: ANN201
    start_time=0,  # noqa: ANN001
    end_time=20,  # noqa: ANN001
    n_cars=500,  # noqa: ANN001
    seed=42,  # noqa: ANN001
    phase=1,  # noqa: ANN001
    AV_trust=config.mode_choice_model.AV_TRUST,  # noqa: ANN001
    pop_prob=config.population.RIDE_HAILING_POPULATION_PROBABILITIES,  # noqa: ANN001
    allocation=None,  # noqa: ANN001
    EV_penetration=1,  # noqa: ANN001
    AV_penetration=1,  # noqa: ANN001
    returnDataFrame=False,  # noqa: ANN001
    charging_capacity=20,  # noqa: ANN001
    charging_power=50,  # noqa: ANN001
    AV_price_reduction=None,  # noqa: ANN001
    discount_rate=0,  # noqa: ANN001
    MoD_interval_reduction=0,  # noqa: ANN001
    mode_choice_strategy=config.mode_choice_model.MODE_CHOICE_STRATEGY,  # noqa: ANN001
):
    """
    :param price_params_ride_hailing:
    :param AV_trust:
    :param EV_penetration:
    :param allocation:
    :param charging_capacity:
    :param charging_power:
    :param AV_price_reduction:
    :param start_time:
    :param end_time:
    :param n_cars:
    :param n_scooter:
    :param n_kick_scooter:
    :param seed:
    :param substitution:
    :param pop_prob: 1.0 means only price sensitive users, 0.0 means only sustainable users
    :return:
    """

    # Before each simulation run, reset counter and random number generators
    RideHailingCar.ride_hailing_car_id = 0
    RideHailingAV.ride_hailing_av_id = 0
    User.user_id = 0
    DemandFactory.counter = 0

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Init. Simulation Modules.               #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    # Vehicle Choice Model
    if mode_choice_strategy == ModeChoiceStrategy.SUBSTITUTION_AWARE:
        vehicle_choice_model = OnlyCarVehicleChoiceBehavior(
            ["RideHailingCar", "AutonomousCar"]
        )

    else:
        raise NotImplementedError("Other Vehicle Choice Models not Implemented yet.")

    # Population Type
    population_factory = PopulationFactory(pop_prob)

    Tracking.init(env)

    charging_infrastructure = ChargingInfrastructure(
        env,
        config.charging_infrastructure.LOCATIONS,
        config.charging_infrastructure.CHARGING_STATION_POWER,
        config.charging_infrastructure.CHARGING_STATION_CAPACITY,
        config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE,
        reset=True,
    )

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Load Vehicle Fleet and Place on World.  #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    supply_prob = pd.read_csv(config.path.PATH_VEHICLE_SUPPLY)

    ride_hailing_fleet_config_0 = generate_ridehailing_fleet_config(
        distribution=supply_prob, n_cars=n_cars, n_AVs=n_cars
    )
    ride_hailing_fleet_0 = generate_mixed_ride_hailing_fleet(
        env, ride_hailing_fleet_config_0
    )

    ride_hailing_fleet_config_1 = generate_ridehailing_fleet_config(
        distribution=supply_prob, n_cars=n_cars, n_AVs=n_cars
    )
    ride_hailing_fleet_1 = generate_mixed_ride_hailing_fleet(
        env, ride_hailing_fleet_config_1
    )

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Operations Management Processes         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    available_vehicle_modes_ridehailing = ["RideHailingCar", "AutonomousCar"]
    available_vehicle_modes_supply_ride_hailing = [n_cars, n_cars]

    # if queue sizes at charging stations are all zero, we should account for that in the operations
    # there can be more clever and nuanced approaches, but as a rule of thumb, we should not allow operations to send vehicles to charging stations that are full if we don't allow queueing
    allow_queue = sum(config.charging_infrastructure.CHARGING_STATION_QUEUE_SIZE) > 0

    # Initialize Rule Based Relocation Scheduler
    # For RideHailing Fleets
    ridehailing_operations_0 = RideHailingBaseChargingOperations(
        env=env,
        distance_matrix=distance_matrix,
        time_between_operations=config.ride_hailing_operators[0].OPERATIONS_START,
        operation_duration=config.ride_hailing_operators[0].OPERATIONS_DURATION,
        available_modes=available_vehicle_modes_ridehailing,
        available_modes_supply=available_vehicle_modes_supply_ride_hailing,
        state_of_charge_threshold=config.ride_hailing_operators[0].RECHARGE_THRESHOLD,
        allow_queue=allow_queue,
    )

    ridehailing_operations_1 = RideHailingBaseChargingOperations(
        env=env,
        distance_matrix=distance_matrix,
        time_between_operations=config.ride_hailing_operators[0].OPERATIONS_START,
        operation_duration=config.ride_hailing_operators[0].OPERATIONS_DURATION,
        available_modes=available_vehicle_modes_ridehailing,
        available_modes_supply=available_vehicle_modes_supply_ride_hailing,
        state_of_charge_threshold=config.ride_hailing_operators[0].RECHARGE_THRESHOLD,
        allow_queue=allow_queue,
    )

    # Operator Modules
    search_engine = {
        "ride_hailing_0": RideHailingSearchEngine(env),
        "ride_hailing_1": RideHailingSearchEngine(env),
    }

    vehicle_assignment_engine = {
        "ride_hailing_0": RideHailingAllocationEngine(env),
        "ride_hailing_1": RideHailingAllocationEngine(env),
    }

    ridehailing_operator_0 = RideHailingOperator(
        env=env,
        fleet=ride_hailing_fleet_0,
        charging_infrastructure=charging_infrastructure,
        operations=ridehailing_operations_0,
        search_engine=search_engine["ride_hailing_0"],
        allocation_engine=vehicle_assignment_engine["ride_hailing_0"],
    )

    ridehailing_operator_1 = RideHailingOperator(
        env=env,
        fleet=ride_hailing_fleet_1,
        charging_infrastructure=charging_infrastructure,
        operations=ridehailing_operations_1,
        search_engine=search_engine["ride_hailing_1"],
        allocation_engine=vehicle_assignment_engine["ride_hailing_1"],
    )

    payment_engine = {
        "ride_hailing_0": ridehailing_operator_0,
        "ride_hailing_1": ridehailing_operator_1,
    }

    # World
    world = World.init(
        env,
        search_engine,
        payment_engine,
        vehicle_assignment_engine,
        vehicle_choice_model,
        population_factory,
        charging_infrastructure,
        reset=True,
    )

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Spawn Demand Processes.                 #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #

    ride_hailing_demand_factory = DemandFactory(
        env, world, config.path.PATH_DEMAND_MODIFIERS, mode="ride_hailing"
    )

    env.process(ride_hailing_demand_factory.generate_demand())

    # # # # # # # # # # # # # # # # # # # # # #
    #                                         #
    # Run Simulation.                         #
    #                                         #
    # # # # # # # # # # # # # # # # # # # # # #
    logging.warning("Starting Simulation.", extra={"clazz": "main", "oid": ""})

    env.run(until=end_time)

    logging.warning("Simulation Finished.", extra={"clazz": "main", "oid": ""})

    total_cost_per_day = {
        "ride_hailing_0": (
            config.ride_hailing_vehicles.get("RideHailingCar").DAILY_TOTAL_COST
            * AV_penetration
            * n_cars
        )
        * (end_time / 1440),
        "ride_hailing_1": (
            config.ride_hailing_vehicles.get("RideHailingCar").DAILY_TOTAL_COST
            * AV_penetration
            * n_cars
        )
        * (end_time / 1440),
    }

    # Daily Total Cost (CAPEX+OPEX) (cost derived from RevCalc excel in iCloud folder)
    no_vehicles_to_be_charged = {
        "ride_hailing_0": ride_hailing_fleet_0.count_vehicles_below_soc_level(
            config.ride_hailing_operators[0].RECHARGE_THRESHOLD
        ),
        "ride_hailing_1": ride_hailing_fleet_1.count_vehicles_below_soc_level(
            config.ride_hailing_operators[0].RECHARGE_THRESHOLD
        ),
    }

    total_operational_cost = {
        "ride_hailing_0": ride_hailing_fleet_0.get_operational_costs(),
        "ride_hailing_1": ride_hailing_fleet_1.get_operational_costs(),
    }

    # Final Objective Function for Heuristic Search
    func_objective = {
        "ride_hailing_0": ridehailing_operator_0.total_revenue
        - total_cost_per_day["ride_hailing_0"]
        - ridehailing_operator_0.total_missed_revenue
        - total_operational_cost["ride_hailing_0"],
        "ride_hailing_1": ridehailing_operator_1.total_revenue
        - total_cost_per_day["ride_hailing_1"]
        - ridehailing_operator_1.total_missed_revenue
        - total_operational_cost["ride_hailing_1"],
    }
    transactions = {
        "ride_hailing_0": ridehailing_operator_0.transaction_df,
        "ride_hailing_1": ridehailing_operator_1.transaction_df,
    }

    if config.settings.PERSIST_RESULTS:
        transactions["ride_hailing_0"].to_csv(
            Path(
                config.path.OUTPUT_FOLDER,
                "ride_hailing_0_"
                + scenario_name
                + "_"
                + "phase_"
                + str(phase)
                + "_"
                + config.path.TRANSACTION_FILE,
            ),
            index=False,
        )
        transactions["ride_hailing_1"].to_csv(
            Path(
                config.path.OUTPUT_FOLDER,
                "ride_hailing_1_"
                + scenario_name
                + "_"
                + "phase_"
                + str(phase)
                + "_"
                + config.path.TRANSACTION_FILE,
            ),
            index=False,
        )

    if returnDataFrame:
        # Persist Results
        result = {
            "fleet_size": [n_cars],
            "charging_capacity": [charging_capacity],
            "charging_power": [charging_power],
            "pop_prob": [pop_prob],
            "AV_trust": [AV_trust],
            "AV_penetration": [AV_penetration],
            "AV_price_reduction": [AV_price_reduction],
            "MCA_adjuster": [MoD_interval_reduction],
            "discount_rate": [discount_rate],
            "seed": [seed],
            "phase": [phase],
            "total_revenue_ride_hailing": [ridehailing_operator_0.total_revenue],
            "total_cost_per_day_ride_hailing": [total_cost_per_day["ride_hailing_0"]],
            "total_operational_cost_per_day_ride_hailing": total_operational_cost[
                "ride_hailing_0"
            ],
            "total_profit_ride_hailing": [
                ridehailing_operator_0.total_revenue
                - total_cost_per_day["ride_hailing_0"]
                - total_operational_cost["ride_hailing_0"]
            ],
            "total_trips_ride_hailing": len(world.users),
            "total_fulfilled_trips_ride_hailing": [
                ridehailing_operator_0.total_fulfilled_trips
            ],
            "total_missed_trips_ride_hailing": [
                ridehailing_operator_0.total_missed_trips
            ],
            "total_missed_revenue_ride_hailing": [
                ridehailing_operator_0.total_missed_revenue
            ],
        }

        transactions = transactions["ride_hailing_0"]
        # Calculate performance indicators per mode
        indicators_per_mode = (
            transactions[transactions["selected_vehicle_mode"] != "None"]
            .groupby(["selected_vehicle_mode"])
            .agg(
                {
                    "price": "sum",
                    "duration": "sum",
                    "distance": "sum",
                    "energy_consumption": "sum",
                    "waiting_time": "sum",
                    "pick_up_time": "sum",
                }
            )
        )

        # Count Trips by Vehicle Type
        overall_rentals = pd.DataFrame(result)
        available_modes = [
            "RideHailingCar_True",
            "RideHailingCar_False",
            "AutonomousCar_True",
        ]
        for mode in available_modes:
            rentals = (
                transactions[transactions["selected_vehicle_mode"] == mode]
                .groupby("state")
                .agg({"RideHailingCar": "sum", "AutonomousCar": "sum"})
                .reset_index(drop=True)
            )
            rentals = rentals.add_prefix(f"{mode}_")
            overall_rentals = pd.concat([overall_rentals, rentals], axis=1)
            # "RideHailingCar_True": "sum", "RideHailingCar_False": "sum", "AutonomousCar_True": "sum"
            # Prepare KPI per Mode (Distance, Duration, Revenue)
            try:
                kpi_for_mode = indicators_per_mode.loc[[mode]].reset_index(drop=True)
            except Exception:
                kpi_for_mode = pd.DataFrame(
                    pd.Series(
                        {
                            "price": 0,
                            "duration": 0,
                            "distance": 0,
                            "energy_consumption": 0,
                            "waiting_time": 0,
                            "pick_up_time": 0,
                        }
                    )
                ).transpose()
            kpi_for_mode.rename(
                columns={"price": "revenue"}, inplace=True
            )  # to avoid future confusion
            kpi_for_mode = kpi_for_mode.add_prefix(f"{mode}_")
            overall_rentals = pd.concat([overall_rentals, kpi_for_mode], axis=1)

        return overall_rentals
    else:
        return (
            ridehailing_operator_0.total_revenue,
            total_cost_per_day["ride_hailing_0"],
            total_operational_cost["ride_hailing_0"],
            ridehailing_operator_0.total_revenue
            - total_cost_per_day["ride_hailing_0"]
            - total_operational_cost["ride_hailing_0"],
            ridehailing_operator_0.total_fulfilled_trips,
            ridehailing_operator_0.total_missed_trips,
            no_vehicles_to_be_charged["ride_hailing_0"],
            func_objective["ride_hailing_0"],
            ridehailing_operator_1.total_revenue,
            total_cost_per_day["ride_hailing_1"],
            total_operational_cost["ride_hailing_1"],
            ridehailing_operator_1.total_revenue
            - total_cost_per_day["ride_hailing_1"]
            - total_operational_cost["ride_hailing_1"],
            ridehailing_operator_1.total_fulfilled_trips,
            ridehailing_operator_1.total_missed_trips,
            no_vehicles_to_be_charged["ride_hailing_1"],
            func_objective["ride_hailing_1"],
        )


### Single Run

TECH_SHARE = [0.25, 0.5, 0.75, 1.0]
USER_SHARES = [0.247, 0.237, 0.19, 0.325]
scenario_name = "single_P_analysis"
# AV_trust_analysis, population_analysis, fleet_size_analysis, charging_capacity_analysis, tech_phase_analysis
phase = 1

result = run_single_simulation(
    end_time=600,
    n_cars=100,
    seed=4711,
    phase=phase,
    pop_prob=USER_SHARES,
    EV_penetration=TECH_SHARE[phase],
    charging_power=config.charging_infrastructure.CHARGING_STATION_POWER,
    charging_capacity=config.charging_infrastructure.CHARGING_STATION_CAPACITY,
    AV_penetration=TECH_SHARE[phase],
    returnDataFrame=False,
)


# TECH_SHARE = [0.25, 0.5, 0.75, 1.0]
# USER_SHARES = [0.247, 0.237, 0.19, 0.325]
# random.seed(42)
# seeds = random.sample(range(1000), 10)
# scenario_name = "single_P_analysis"
# phase = 3
# for seed in seeds[1:]:
#     a = run_single_simulation(
#         end_time=1400 * 1,
#         n_cars=500,
#         seed=seed,
#         phase=phase,
#         pop_prob=USER_SHARES,
#         EV_penetration=TECH_SHARE[phase],
#         charging_capacity=5,
#         AV_penetration=TECH_SHARE[phase],
#         returnDataFrame=False,
#         charging_power=10,
#     )

#     print(a)

# Simulation Experiments
# Random Variables for our Monte Carlo Run


# random.seed(42)
# seeds = random.sample(range(1000), 10)

# # Store all simulation results in this data frame
# all_simulations = pd.DataFrame()
# sim_days = 1
# scenario_name = "single_P_analysis"
# # AV_trust_analysis, population_analysis, fleet_size_analysis, charging_capacity_analysis, tech_phase_analysis
# TECH_SHARE = [0.25, 0.5, 0.75, 1.0]
# phases = [0, 1, 2, 3]

# # Real Run

# if __name__ == "__main__":
#     T = 1440 * sim_days
#
#     # single phase
#     for phase in range(0, 101, 5):
#         phase /= 100
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'seed': seed,
#                          'phase': phase,
#                          'EV_penetration': phase,
#                          'AV_penetration': phase, 'returnDataFrame': True,
#                          })
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})
#
#         # After each seed save
#         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

### This is for analysing different proportion of user population
# for pop_type in range(4):
#     for user_share in range(11):
#
#         POP_PROB = [(10 - user_share) / 3 * 0.1, (10 - user_share) / 3 * 0.1, (10 - user_share) / 3 * 0.1,
#                     (10 - user_share) / 3 * 0.1]
#         POP_PROB[pop_type] = user_share * 0.1
#         for phase in phases:
#             data = []
#             for idx, seed in enumerate(seeds):
#                 data.append({'end_time': T, 'seed': seed,
#                              'phase': phase, 'pop_prob': POP_PROB,
#                              'EV_penetration': TECH_SHARE[phase],
#                              'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True})
#             sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                            mp_context=mp.get_context('spawn'))
#             for i in range(len(sim_res)):
#                 all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#             logging.error("seed: {}, idx: {}".format(seed, idx),
#                           extra={"clazz": "main", "oid": ""})

# After each seed save
# all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

### This is for analysing different AV_trust values

# for a_1 in [2, 4, 6, 8]:
#     for a_2 in [2, 4, 6, 8]:
#         for a_3 in [2, 4, 6, 8]:
#             for a_4 in [2, 4, 6, 8]:
#                 AV_TRUST = [a_1, a_2, a_3, a_4]
#                 for phase in phases:
#                     data = []
#                     for idx, seed in enumerate(seeds):
#                         data.append({'end_time': T, 'seed': seed,
#                                      'phase': phase, "AV_trust": AV_TRUST,
#                                      'EV_penetration': TECH_SHARE[phase],
#                                      'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True})
#                     sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                                    mp_context=mp.get_context('spawn'))
#                     for i in range(len(sim_res)):
#                         all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#                     logging.error("seed: {}, idx: {}".format(seed, idx),
#                                   extra={"clazz": "main", "oid": ""})
#
#                     # After each seed save
#                     all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'),
#                                            index=False)

### This is for analysing different fleet sizes

# for fleet_size in [200, 300, 400, 500, 600, 700, 800, 1000]:
#     for phase in phases:
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'n_cars': fleet_size, 'seed': seed,
#                          'phase': phase,
#                          'EV_penetration': TECH_SHARE[phase],
#                          'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True})
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})

# After each seed save
# all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

# # This is for analysing different charging power
# POP_PROB = SHARES[0]
# for fleet_size in [200, 300, 400, 500, 600, 700, 800, 1000]:
#     for charging_capacity in [1, 4, 5, 10, 20]:
#         for charging_power in [5, 10, 22, 50]:
#             for phase in phases:
#                 data = []
#                 for idx, seed in enumerate(seeds):
#                     data.append({'end_time': T, 'n_cars': fleet_size, 'seed': seed,
#                                  'phase': phase, 'pop_prob': POP_PROB,
#                                  'EV_penetration': TECH_SHARE[phase], "charging_capacity": charging_capacity,
#                                  'AV_penetration': TECH_SHARE[phase], 'returnDataFrame': True,
#                                  'charging_power': charging_power})
#                 sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                                mp_context=mp.get_context('spawn'))
#                 for i in range(len(sim_res)):
#                     all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#                 logging.error("seed: {}, idx: {}".format(seed, idx),
#                               extra={"clazz": "main", "oid": ""})
#
#                 # After each seed save
#                 all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

# print("FINISHED")

# for pop_prob in [[1.0, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]:
#     for phase in range(0, 101, 5):
#         phase /= 100
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'seed': seed,
#                          'phase': phase, 'pop_prob': pop_prob,
#                          'EV_penetration': phase,
#                          'AV_penetration': phase, 'returnDataFrame': True,
#                          })
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})
#
#         # After each seed save
#         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

# AV_price
# for phase in [25,50,75,100]:
#     phase = phase/100
#     for AV_price_fraction in range(3, 10):
#         AV_price_fraction /= 10
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'seed': seed, 'discount_rate': 0,
#                          'phase': phase, 'AV_price_reduction': AV_price_fraction,
#                          'EV_penetration': phase,
#                          'AV_penetration': phase, 'returnDataFrame': True
#                          })
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})
#
#         # After each seed save
#         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

# MCA_P
# for phase in [25,50,75,100]:
#     phase = phase/100
#     for MCA_reduction in range(0, 10):
#         MCA_reduction /= 10
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'seed': seed, 'discount_rate': 0,
#                          'phase': phase,
#                          'EV_penetration': phase, 'MoD_interval_reduction': MCA_reduction,
#                          'AV_penetration': phase, 'returnDataFrame': True
#                          })
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})
#
#         # After each seed save
#
#         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

### FS_UP
# for pop_prob in [[1.0, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]:
#     for AVT in range(0, 10):
#         AV_TRUST = [AVT, AVT, AVT, AVT]
#         phase = 0.5
#         data = []
#         for idx, seed in enumerate(seeds):
#             data.append({'end_time': T, 'seed': seed,
#                          'phase': phase, 'pop_prob': pop_prob,
#                          'EV_penetration': phase, 'AV_trust': AV_TRUST,
#                          'AV_penetration': phase, 'returnDataFrame': True,
#                          })
#         sim_res = pqdm(data, run_single_simulation, n_jobs=10, argument_type='kwargs',
#                        mp_context=mp.get_context('spawn'))
#         for i in range(len(sim_res)):
#             all_simulations = pd.concat([all_simulations, sim_res[i]], axis=0)
#         logging.error("seed: {}, idx: {}".format(seed, idx),
#                       extra={"clazz": "main", "oid": ""})
#
#         # After each seed save
#         all_simulations.to_csv(Path(output_folder, scenario_name + '_simulation_results.csv'), index=False)

# print("FINISHED")
