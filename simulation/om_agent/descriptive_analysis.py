import json
import pandas as pd
import matplotlib.pyplot as plt
import os
from pathlib import Path
import sys
from configparser import ConfigParser
import os
import geojson
import plotly.express as px

import matplotlib as mp

class DescriptiveAnalysis:

    def __init__(self, temporal_res, spatial_res, episode, idx, folder_name, rolling_window, kpi_tracker_service_worker_suffix):
        self.simulation_results = \
            pd.read_csv(os.path.join("all_simulation_results.csv"))
        self.kpi_tracker_results = \
            pd.read_csv(os.path.join(f"simulation\\om_agent\\results\\kpi_tracker_results.csv"))
        self.agent_results_car = \
            pd.read_csv(os.path.join("simulation", "om_agent", "results", "0_results_car.csv"))
        self.agent_results_scooter = \
            pd.read_csv(os.path.join("simulation", "om_agent", "results", "0_results_scooter.csv"))
        self.agent_results_kickscooter = \
            pd.read_csv(os.path.join("simulation", "om_agent", "results", "0_results_kickscooter.csv"))

        self.car_agent_behaviour = pd.read_csv(os.path.join("simulation", "om_agent", "results", "car_agent_behaviour_results.csv"))
        self.scooter_agent_behaviour = pd.read_csv(
            os.path.join("simulation", "om_agent", "results", "scooter_agent_behaviour_results.csv"))
        self.kickscooter_agent_behaviour = pd.read_csv(
            os.path.join("simulation", "om_agent", "results", "kickscooter_agent_behaviour_results.csv"))

        self.kpi_tracker_results_service_worker = pd.read_csv(os.path.join(f"simulation\\om_agent\\results\\kpi_tracker_results{kpi_tracker_service_worker_suffix}.csv"))

        self.temporal_res = temporal_res
        self.spatial_res = spatial_res
        self.episode = episode
        self.rolling_window = rolling_window
        self.geojson_path = os.path.join('data',
                                         'environment',
                                         'geodesic',
                                         f'env_hex_{self.spatial_res}.geojson')
        # create folder for storage
        self.folder_name = folder_name
        os.makedirs(folder_name)

        self.numerical_assessment_file_path = os.path.join(self.folder_name, f'numerical_assessment_calculations.txt')
        
        
        # save files and models
        self.kpi_tracker_results.to_csv(os.path.join(self.folder_name, f'kpi_tracker_results.csv'))
        self.agent_results_car.to_csv(os.path.join(self.folder_name, '0_results_car.csv'))
        self.agent_results_scooter.to_csv(os.path.join(self.folder_name, '0_results_scooter.csv'))
        self.agent_results_kickscooter.to_csv(os.path.join(self.folder_name, '0_results_kickscooter.csv'))

        self.simulation_results.to_csv(os.path.join(self.folder_name, 'all_simulation_results.csv'))
        model_path = os.path.join('simulation', 'om_agent', 'results', 'models')
        shutil.copyfile(os.path.join(model_path, os.listdir(model_path)[0]), os.path.join(self.folder_name,os.listdir(model_path)[0]))
        shutil.copyfile(os.path.join(model_path, os.listdir(model_path)[1]),
                        os.path.join(self.folder_name, os.listdir(model_path)[1]))
        shutil.copyfile(os.path.join(model_path, os.listdir(model_path)[2]),
                        os.path.join(self.folder_name, os.listdir(model_path)[2]))

        base_regions =  parser.get("SHARED_VEHICLE_OPERATOR", "BASE_REGIONS")
        self.charging_stations = base_regions.split(',')

        self.episode_duration = parser.getint("WORLD", "days_per_episode")*24*60
        self._number_cars = parser.getint("SHARED_CAR", "n_vehicles")
        self._number_scooters = parser.getint("SHARED_SCOOTER", "n_vehicles")
        self._number_kickscooters = parser.getint("SHARED_KICK_SCOOTER", "n_vehicles")
        self._number_vehicles = self._number_cars + self._number_scooters + self._number_kickscooters

        # read geojson file
        with open(self.geojson_path) as f:
            self.geojson_obj = geojson.load(f)
            
        acceptance_rate = parser.get("CHARGING_OPTIMIZATION", "charging_assignment_acceptance")
        charging_station_allocation = parser.get("SHARED_VEHICLE_OPERATOR", "allocation")

        self.sensitivity_analysis_file_path = os.path.join(self.folder_name, f'sensitivity_results_{self._number_cars}_{acceptance_rate}_{charging_station_allocation}.txt')

    def thesis_numerical_assessment_plots(self):
        ###################################### objective (vehicles below critical threshold)###########################
        fig, axs = plt.subplots(3, 1, constrained_layout=True, figsize=(10, 8))

        fig.suptitle("Vehicle fleet battery KPIs", fontsize=16, fontweight='bold')


        ############################### CARS ########################################
        axs[0].bar(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['episode'].unique()[:-1],
                   self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0].groupby(['episode'])
                    .agg({'number_of_vehicles_below_critical_soc_treshold_car':'max'})
                        ['number_of_vehicles_below_critical_soc_treshold_car'][:-1], label='Maximum number of vehicles below critical SOC', color='cornflowerblue')

        ax2 = axs[0].twinx()
        ax2.plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['episode'].unique()[:-1],
                   self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0].groupby(['episode'])
                    .agg({'sum_soc_car':'min'})
                        ['sum_soc_car'][:-1]/16.7/self._number_cars, label='Minimum average vehicle SOC (%)', color='red')

        #axs[0].legend()
        #ax2.legend()
        #axs[0].set_xlabel('Episode')
        axs[0].set_ylabel('Quantity')
        ax2.set_ylabel('SOC (%)')
        axs[0].set_title('Cars')

        ############################### SCOOTERS ########################################

        axs[1].bar(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['episode'].unique()[:-1],
                   self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0].groupby(['episode'])
                   .agg({'number_of_vehicles_below_critical_soc_treshold_scooter': 'max'})
                   ['number_of_vehicles_below_critical_soc_treshold_scooter'][:-1],
                   label='Maximum number of vehicles below critical SOC', color='cornflowerblue')

        ax2 = axs[1].twinx()
        ax2.plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['episode'].unique()[:-1],
                 self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0].groupby(['episode'])
                 .agg({'sum_soc_scooter': 'min'})
                 ['sum_soc_scooter'][:-1] / 4.8 / self._number_scooters, label='Minimum average vehicle SOC (%)', color='red')

        #axs[1].legend()
        #ax2.legend()
        # axs[0].set_xlabel('Episode')
        axs[1].set_ylabel('Quantity')
        ax2.set_ylabel('SOC (%)')
        axs[1].set_title('Scooters')

        ############################### KICKSCOOTER ########################################

        axs[2].bar(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['episode'].unique()[:-1],
                   self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0].groupby(['episode'])
                   .agg({'number_of_vehicles_below_critical_soc_treshold_kickscooter': 'max'})
                   ['number_of_vehicles_below_critical_soc_treshold_kickscooter'][:-1],
                   label='Maximum number of vehicles below critical SOC', color='cornflowerblue')

        ax2 = axs[2].twinx()
        ax2.plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['episode'].unique()[:-1],
                 self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0].groupby(['episode'])
                 .agg({'sum_soc_kickscooter': 'min'})
                 ['sum_soc_kickscooter'][:-1] / 0.288 / self._number_kickscooters, label='Minimum average vehicle SOC (%)', color='red')

        #axs[2].legend()
        #ax2.legend()
        axs[2].set_xlabel('Episode')

        axs[2].legend(loc='upper center', bbox_to_anchor=(0.5, -0.25))
        ax2.legend(loc='upper center', bbox_to_anchor=(0.447, -0.4))

        axs[2].set_ylabel('Quantity')
        ax2.set_ylabel('SOC (%)')
        axs[2].set_title('Kick-Scooters')

        plt.savefig(os.path.join(self.folder_name, 'thesis_numerical_assessment_objective.png'))
        plt.show()


        ########################operator KPIS####################################################################
        fig, axs = plt.subplots(2, 1, constrained_layout=True, figsize=(10, 8))

        fig.suptitle("Operator KPIs", fontsize=16, fontweight='bold')

        axs[0].plot(self.simulation_results['total_revenue'].iloc[1:], label='Total Revenue', color='g')
        axs[0].plot(self.simulation_results['total_revenue'].iloc[1:].rolling(window=15).mean(), label='Moving Average', color='black')
        axs[0].legend()
        axs[0].set_xlabel('Episode')
        axs[0].set_ylabel('Euro')

        axs[1].plot(self.simulation_results['total_missed_trips'].iloc[1:], label='Missed Trips', color='r')
        axs[1].plot(self.simulation_results['total_missed_trips'].iloc[1:].rolling(window=15).mean(), label='Moving Average', color='black')
        axs[1].legend()
        axs[1].set_xlabel('Episode')
        axs[1].set_ylabel('Quantity')

        plt.savefig(os.path.join(self.folder_name, 'thesis_numerical_assessment_operator_kpis.png'))
        plt.show()
    
    def sensitivity_analysis_demand_side(self):

        # ATTENTION: main_charging line 67 needs to be set to 3!!
        df_benchmark_simple_mean = self.kpi_tracker_results[self.kpi_tracker_results['episode'] < 3].groupby(
            'env_time').mean().reset_index()
        
        df_agent_mean = self.kpi_tracker_results[self.kpi_tracker_results['episode'] >= 3].groupby(
            'env_time').mean().reset_index()
        
        # DYNAMIC ASSIGNMENT
        cars_below_soc_dynamic = df_agent_mean['number_of_vehicles_below_critical_soc_treshold_car'].mean()
        cars_avg_soc_dynamic = df_agent_mean['sum_soc_car'].mean() /self._number_cars / 16.7 * 100
        scooters_below_soc_dynamic = df_agent_mean['number_of_vehicles_below_critical_soc_treshold_scooter'].mean()
        scooters_avg_soc_dynamic = df_agent_mean['sum_soc_scooter'].mean() /self._number_scooters / 4.8 * 100
        operator_revenue_dynamic = self.simulation_results['total_revenue'].iloc[3:].mean()
        operator_missed_dynamic = self.simulation_results['total_missed_trips'].iloc[3:].mean()
        
        # STATIC ASSIGNMENT
        cars_below_soc_static = df_benchmark_simple_mean['number_of_vehicles_below_critical_soc_treshold_car'].mean()
        cars_avg_soc_static = df_benchmark_simple_mean['sum_soc_car'].mean()/self._number_cars / 16.7 * 100
        scooters_below_soc_static = df_benchmark_simple_mean['number_of_vehicles_below_critical_soc_treshold_scooter'].mean()
        scooters_avg_soc_static = df_benchmark_simple_mean['sum_soc_scooter'].mean()/self._number_scooters / 4.8 * 100
        operator_revenue_static = self.simulation_results['total_revenue'].iloc[:3].mean()
        operator_missed_static = self.simulation_results['total_missed_trips'].iloc[:3].mean()

        with open(self.sensitivity_analysis_file_path, 'w') as f:
            f.write(f"cars_below_soc_dynamic: {cars_below_soc_dynamic}\n" +
                    f"cars_avg_soc_dynamic: {cars_avg_soc_dynamic}\n"+
                    f"scooters_below_soc_dynamic: {scooters_below_soc_dynamic}\n"+
                    f"scooters_avg_soc_dynamic: {scooters_avg_soc_dynamic}\n"+
                    f"operator_revenue_dynamic: {operator_revenue_dynamic}\n"+
                    f"operator_missed_dynamic: {operator_missed_dynamic}\n"+
                    f"cars_below_soc_static: {cars_below_soc_static}\n"+
                    f"cars_avg_soc_static: {cars_avg_soc_static}\n"+
                    f"scooters_below_soc_static: {scooters_below_soc_static}\n"+
                    f"scooters_avg_soc_static: {scooters_avg_soc_static}\n"+
                    f"operator_revenue_static: {operator_revenue_static}\n"+
                    f"operator_missed_static: {operator_missed_static}\n"
                    )


    def sensitivity_analysis_service_worker(self):

        df_benchmark_service_worker_mean = self.kpi_tracker_results_service_worker.groupby(
            'env_time').mean().reset_index()

        # SERVICE WORKER
        cars_below_soc_service_worker = df_benchmark_service_worker_mean['number_of_vehicles_below_critical_soc_treshold_car'].mean()
        cars_avg_soc_service_worker = df_benchmark_service_worker_mean['sum_soc_car'].mean()/self._number_cars / 16.7 * 100
        scooters_below_soc_service_worker = df_benchmark_service_worker_mean['number_of_vehicles_below_critical_soc_treshold_scooter'].mean()
        scooters_avg_soc_service_worker = df_benchmark_service_worker_mean['sum_soc_scooter'].mean() /self._number_scooters / 4.8 * 100
        operator_revenue_service_worker = self.simulation_results['total_revenue'].mean()
        operator_missed_service_worker = self.simulation_results['total_missed_trips'].mean()

        with open(self.sensitivity_analysis_file_path, 'w') as f:
            f.write(f"cars_below_soc_service_worker: {cars_below_soc_service_worker}\n" +
                    f"cars_avg_soc_service_worker: {cars_avg_soc_service_worker}\n"+
                    f"scooters_below_soc_service_worker: {scooters_below_soc_service_worker}\n"+
                    f"scooters_avg_soc_service_worker: {scooters_avg_soc_service_worker}\n"+
                    f"operator_revenue_service_worker: {operator_revenue_service_worker}\n"+
                    f"operator_missed_service_worker: {operator_missed_service_worker}\n"
                    )

    def sensitivity_analysis_three_charging_strategies(self):

        df_benchmark_service_worker = self.kpi_tracker_results_service_worker.groupby(
            'env_time').mean().reset_index()

        df_benchmark_simple = self.kpi_tracker_results[self.kpi_tracker_results['episode'] < 3].groupby(
            'env_time').mean().reset_index()
        df_agent_mean = self.kpi_tracker_results[self.kpi_tracker_results['episode'] >= 3].groupby(
            'env_time').mean().reset_index()

        # ##########################################Charging KPIs########################################################
        fig, axs = plt.subplots(4, 1, constrained_layout=True, figsize=(12, 14))

        fig.suptitle("Vehicle Fleet Battery KPIs", fontsize=16, fontweight='bold')

        axs[0].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['number_of_vehicles_below_critical_soc_treshold_car'],
                    label='Service Worker Charging', color='slateblue')
        axs[0].plot(df_benchmark_simple['env_time'] / 60,
                    df_benchmark_simple['number_of_vehicles_below_critical_soc_treshold_car'],
                    label='Static Demand-Side Rebalancing Policy', color='darkorange')
        axs[0].plot(df_agent_mean['number_of_vehicles_below_critical_soc_treshold_car'],
                    label='Dynamic Demand-Side Rebalancing Policy', color='g',
                    linewidth=3)
        axs[0].set_title('Cars below critical SOC')

        # axs[0].legend()
        axs[0].set_ylabel('Quantity')

        axs[1].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['sum_soc_car'] / self._number_cars / 16.7,
                    label='Service Worker Charging', color='slateblue')
        axs[1].plot(df_benchmark_simple['env_time'] / 60, df_benchmark_simple['sum_soc_car'] / self._number_cars / 16.7,
                    label='Static Demand-Side Rebalancing Policy', color='darkorange')

        axs[1].plot(df_agent_mean['sum_soc_car'] / self._number_cars / 16.7,
                    label='Dynamic Demand-Side Rebalancing Policy', color='g', linewidth=3)
        axs[1].set_title('Cars battery capacity')
        # axs[1].legend()
        axs[1].set_ylabel('%')

        #############################################scooter#######################################################
        axs[2].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['number_of_vehicles_below_critical_soc_treshold_scooter'],
                    label='Service Worker Charging', color='slateblue')
        axs[2].plot(df_benchmark_simple['env_time'] / 60,
                    df_benchmark_simple['number_of_vehicles_below_critical_soc_treshold_scooter'],
                    label='Static Demand-Side Rebalancing Policy', color='darkorange')
        axs[2].plot(df_agent_mean['number_of_vehicles_below_critical_soc_treshold_scooter'],
                    label='Dynamic Demand-Side Rebalancing Policy', color='g',
                    linewidth=3)
        axs[2].set_title('Scooters below critical SOC')

        # axs[0].legend()
        axs[2].set_ylabel('Quantity')


        axs[3].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['sum_soc_scooter'] / self._number_scooters / 4.8,
                    label='Service Worker Charging', color='slateblue')
        axs[3].plot(df_benchmark_simple['env_time'] / 60,
                    df_benchmark_simple['sum_soc_scooter'] / self._number_scooters / 4.8,
                    label='Static Demand-Side Rebalancing Policy', color='darkorange')

        axs[3].plot(df_agent_mean['sum_soc_scooter'] / self._number_scooters / 4.8,
                    label='Dynamic Demand-Side Rebalancing Policy', color='g', linewidth=3)
        axs[3].set_title('Scooters battery capacity')
        # axs[1].legend()
        axs[3].set_ylabel('%')

        axs[3].legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2)

        plt.savefig(os.path.join(self.folder_name, 'charging_kpis_scooter.png'))
        plt.show()


    def thesis_results(self):

        df_benchmark_service_worker = self.kpi_tracker_results_service_worker[
            self.kpi_tracker_results_service_worker['episode'] == 0]
        
        df_benchmark_simple = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]
        df_agent_mean = self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0].groupby(
            'env_time').mean().reset_index()
        
        # ##########################################Charging KPIs########################################################
        fig, axs = plt.subplots(3, 1, constrained_layout=True, figsize=(10, 8))

        fig.suptitle("Car Battery KPIs", fontsize=16, fontweight='bold')


        axs[0].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['number_of_vehicles_below_critical_soc_treshold_car'],
                    label='Service Worker Charging', color='slateblue')
        axs[0].plot(df_benchmark_simple['env_time'] / 60,
                    df_benchmark_simple['number_of_vehicles_below_critical_soc_treshold_car'],
                    label='Static Demand-Side Rebalancing Policy', color='darkorange')
        axs[0].plot(df_agent_mean['number_of_vehicles_below_critical_soc_treshold_car'], label='Dynamic Demand-Side Rebalancing Policy', color='g',
                    linewidth=3)
        axs[0].set_title('Vehicles below critical SOC per hour')

        #axs[0].legend()
        axs[0].set_ylabel('Quantity')

        axs[1].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['sum_soc_car']/self._number_cars/16.7,
                    label='Service Worker Charging', color='slateblue')
        axs[1].plot(df_benchmark_simple['env_time']/60, df_benchmark_simple['sum_soc_car']/self._number_cars/16.7,label='Static Demand-Side Rebalancing Policy', color='darkorange')

        axs[1].plot(df_agent_mean['sum_soc_car']/self._number_cars/16.7, label='Dynamic Demand-Side Rebalancing Policy', color='g', linewidth=3)
        axs[1].set_title('Average relative fleet battery capacity per hour')
        #axs[1].legend()
        axs[1].set_ylabel('%')


        axs[2].plot(df_benchmark_simple['env_time']/60, df_benchmark_simple['number_of_charging_vehicles_car'], label='Static Demand-Side Rebalancing Policy', color='darkorange')
        axs[2].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['number_of_charging_vehicles_car'],label='Service Worker Charging', color='slateblue')
        axs[2].plot(df_agent_mean['number_of_charging_vehicles_car'], label='Dynamic Demand-Side Rebalancing Policy', color='g', linewidth=3)
        axs[2].set_title('Charging vehicles per hour')
        axs[2].legend(loc='upper center', bbox_to_anchor=(0.5,-0.15), ncol=2)
        axs[2].set_ylabel('Quantity')

        plt.savefig(os.path.join(self.folder_name, 'charging_kpis_car.png'))
        plt.show()

        #############################################scooter#######################################################
        fig, axs = plt.subplots(3, 1, constrained_layout=True, figsize=(10, 8))

        fig.suptitle("Scooter Battery KPIs", fontsize=16, fontweight='bold')

        axs[0].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['number_of_vehicles_below_critical_soc_treshold_scooter'],
                    label='Service Worker Charging', color='slateblue')
        axs[0].plot(df_benchmark_simple['env_time'] / 60,
                    df_benchmark_simple['number_of_vehicles_below_critical_soc_treshold_scooter'],
                    label='Static Demand-Side Rebalancing Policy', color='darkorange')
        axs[0].plot(df_agent_mean['number_of_vehicles_below_critical_soc_treshold_scooter'], label='Dynamic Demand-Side Rebalancing Policy', color='g',
                    linewidth=3)
        axs[0].set_title('Vehicles below critical SOC per hour')

        #axs[0].legend()
        axs[0].set_ylabel('Quantity')

        axs[1].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['sum_soc_scooter']/self._number_scooters/4.8,
                    label='Service Worker Charging', color='slateblue')
        axs[1].plot(df_benchmark_simple['env_time'] / 60, df_benchmark_simple['sum_soc_scooter']/self._number_scooters/4.8,
                    label='Static Demand-Side Rebalancing Policy', color='darkorange')

        axs[1].plot(df_agent_mean['sum_soc_scooter']/self._number_scooters/4.8, label='Dynamic Demand-Side Rebalancing Policy', color='g', linewidth=3)
        axs[1].set_title('Average relative fleet battery capacity per hour')
        #axs[1].legend()
        axs[1].set_ylabel('%')

        axs[2].plot(df_benchmark_simple['env_time'] / 60, df_benchmark_simple['number_of_charging_vehicles_scooter'],
                    label='Static Demand-Side Rebalancing Policy', color='darkorange')
        axs[2].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['number_of_charging_vehicles_scooter'], label='Service Worker Charging',
                    color='slateblue')
        axs[2].plot(df_agent_mean['number_of_charging_vehicles_scooter'], label='Dynamic Demand-Side Rebalancing Policy', color='g', linewidth=3)
        axs[2].set_title('Charging vehicles per hour')
        axs[2].legend(loc='upper center', bbox_to_anchor=(0.5,-0.15), ncol=2)
        axs[2].set_ylabel('Quantity')

        plt.savefig(os.path.join(self.folder_name, 'charging_kpis_scooter.png'))
        plt.show()
        #
        # ##############################################kick scooter##################################################
        fig, axs = plt.subplots(3, 1, constrained_layout=True, figsize=(10, 8))

        fig.suptitle("Kick-Scooter Battery KPIs", fontsize=16, fontweight='bold')

        axs[0].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['number_of_vehicles_below_critical_soc_treshold_kickscooter'],
                    label='Service Worker Charging', color='slateblue')
        axs[0].plot(df_benchmark_simple['env_time'] / 60,
                    df_benchmark_simple['number_of_vehicles_below_critical_soc_treshold_kickscooter'],
                    label='Simple Matching Algorithm', color='darkorange')
        axs[0].plot(df_agent_mean['number_of_vehicles_below_critical_soc_treshold_kickscooter'], label='DQN Agent', color='g',
                    linewidth=3)
        axs[0].set_title('Vehicles below critical SOC per hour')

        #axs[0].legend()
        axs[0].set_ylabel('Quantity')

        axs[1].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['sum_soc_kickscooter']/self._number_kickscooters/0.288,
                    label='Service Worker Charging', color='slateblue')
        axs[1].plot(df_benchmark_simple['env_time'] / 60, df_benchmark_simple['sum_soc_kickscooter']/self._number_kickscooters/0.288,
                    label='Static Demand-Side Rebalancing Policy', color='darkorange')

        axs[1].plot(df_agent_mean['sum_soc_kickscooter']/self._number_kickscooters/0.288, label='Dynamic Demand-Side Rebalancing Policy', color='g', linewidth=3)
        axs[1].set_title('Fleet battery capacity per hour')
        #axs[1].legend()
        axs[1].set_ylabel('%')

        axs[2].plot(df_benchmark_simple['env_time'] / 60, df_benchmark_simple['number_of_charging_vehicles_kickscooter'],
                    label='Static Demand-Side Rebalancing Policy', color='darkorange')
        axs[2].plot(df_benchmark_service_worker['env_time'] / 60,
                    df_benchmark_service_worker['number_of_charging_vehicles_kickscooter'], label='Service Worker Charging',
                    color='slateblue')
        axs[2].plot(df_agent_mean['number_of_charging_vehicles_kickscooter'], label='Dynamic Demand-Side Rebalancing Policy', color='g', linewidth=3)
        axs[2].set_title('Charging vehicles per hour')
        axs[2].legend(loc='upper center', bbox_to_anchor=(0.5,-0.15), ncol=2)
        axs[2].set_ylabel('Quantity')

        plt.savefig(os.path.join(self.folder_name, 'charging_kpis_kickscooter.png'))
        plt.show()



        ############################agent convergence##############################################################

        #############################################car#############################################################

        fig, axs = plt.subplots(1, 2, constrained_layout=True, figsize=(10, 4))

        fig.suptitle("Agent Reward Convergence", fontsize=16, fontweight='bold')
        # cars
        axs[0].plot(
            self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]["avg_car_agent_reward_sum"].rolling(
                window=300).mean(), label='avg_car_agent_reward_sum')
        axs[0].set_title('Car Agent')
        axs[0].set_xlabel('Simulation Hour')
        axs[0].set_ylabel('Average Reward')

        axs[1].plot(
            self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]["avg_scooter_agent_reward_sum"].rolling(
                window=100).mean(), label='avg_scooter_agent_reward_sum')
        axs[1].set_title('Scooter Agent')
        axs[1].set_xlabel('Simulation Hour')
        axs[1].set_ylabel('Average Reward')
        axs[1].set_anchor((0.5,0.0))
        plt.savefig(os.path.join(self.folder_name, 'agent_convergence.png'))
        plt.show()

        # kickscooters
        fig, axs = plt.subplots(1, 2, constrained_layout=True, figsize=(10, 4))

        axs[1].plot(
            self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]["avg_kickscooter_agent_reward_sum"].rolling(
                window=100).mean(), label='avg_kickscooter_agent_reward_sum')
        axs[1].set_title('Kick-Scooter Agent')
        axs[1].set_xlabel('Simulation Hour')
        axs[1].set_ylabel('Average Reward')

        plt.savefig(os.path.join(self.folder_name, 'agent_convergence_kick.png'))
        plt.show()


        #############################################kickscooter#############################################################
        fig, axs = plt.subplots(1, 2, constrained_layout=True, figsize=(10, 4))

        fig.suptitle("Kick-Scooter Agent Convergence", fontsize=16, fontweight='bold')
        # kickscooters
        axs[0].plot(self.agent_results_kickscooter['executed_actions'],
                    self.agent_results_kickscooter['policy_loss'].rolling(window=100).mean(), label='policy_loss')
        axs[0].set_title('Policy Loss ')
        axs[0].set_xlabel('Executed Actions')

        axs[1].plot(
            self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]["avg_kickscooter_agent_reward_sum"].rolling(
                window=100).mean(), label='avg_kickscooter_agent_reward_sum')
        axs[1].set_title('Average Reward')
        axs[1].set_xlabel('Hour')

        plt.savefig(os.path.join(self.folder_name, 'agent_convergence_kickscooters.png'))
        plt.show()

        ####################################### q_value tracking for fixed state #################################
        fig, axs = plt.subplots(3, 1, constrained_layout=True, figsize=(10, 8))

        fig.suptitle("Q-Value Convergence for Fixed State and Charging Station at Destination", fontsize=16, fontweight='bold')

        q_value_columns_with_charging = [column for column in self.agent_results_car if column.startswith('q_value') and 'with_charging' in column]

        # cars
        for q_value in q_value_columns_with_charging:
            axs[0].plot(self.agent_results_car[q_value], label=f"SOC Bucket {q_value[-1]}")
        axs[0].set_title('Car Agent')
        #axs[0].legend()

        # scooters
        for q_value in q_value_columns_with_charging:
            axs[1].plot(self.agent_results_scooter[q_value], label=f"SOC Bucket {q_value[-1]}")
        axs[1].set_title('Scooter Agent')
        #axs[1].legend()

        # kickscooters
        for q_value in q_value_columns_with_charging:
            axs[2].plot(self.agent_results_kickscooter[q_value], label=f"SOC Bucket {q_value[-1]}")
        axs[2].set_title('Kick-Scooter Agent')
        axs[2].legend(loc='upper center', bbox_to_anchor=(0.5,-0.15), ncol=2)

        plt.savefig(os.path.join(self.folder_name, 'agent_convergence_fixed_state_with_charging.png'))
        plt.show()

        ####################################### q_value tracking for fixed state #################################
        fig, axs = plt.subplots(3, 1, constrained_layout=True, figsize=(10, 8))

        q_value_columns_without_charging = [column for column in self.agent_results_car if column.startswith('q_value') and 'without_charging' in column]

        fig.suptitle("Q-Value Convergence for Fixed State without Charging Station at Destination", fontsize=16, fontweight='bold')

        q_value_columns_without_charging = [column for column in self.agent_results_car if column.startswith('q_value') and 'without_charging' in column]

        # cars
        for q_value in q_value_columns_without_charging:
            axs[0].plot(self.agent_results_car[q_value], label=f"SOC Bucket {q_value[-1]}")
        axs[0].set_title('Car Agent')
        #axs[0].legend()

        # scooters
        for q_value in q_value_columns_without_charging:
            axs[1].plot(self.agent_results_scooter[q_value], label=f"SOC Bucket {q_value[-1]}")
        axs[1].set_title('Scooter Agent')
        #axs[1].legend()

        # kickscooters
        for q_value in q_value_columns_without_charging:
            axs[2].plot(self.agent_results_kickscooter[q_value], label=f"SOC Bucket {q_value[-1]}")
        axs[2].set_title('Kick-Scooter Agent')
        axs[2].legend(loc='upper center', bbox_to_anchor=(0.5,-0.15), ncol=2)

        plt.savefig(os.path.join(self.folder_name, 'agent_convergence_fixed_state_without_charging.png'))
        plt.show()


    def episodic_progress(self):


        ############################ charging kpis cars ################################################################
        fig, axs = plt.subplots(4, 1, constrained_layout=True, figsize=(10,8))

        fig.suptitle("Car KPIs", fontsize=16, fontweight='bold')

        axs[0].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['number_of_vehicles_below_critical_soc_treshold_car'], label='agent')
        axs[0].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_vehicles_below_critical_soc_treshold_car'], label='benchmark', color='black')
        axs[0].set_title('Number of vehicles below critical threshold per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_vehicles_below_critical_soc_treshold_car'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_vehicles_below_critical_soc_treshold_car'].max()
        axs[0].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[0].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')
        #axs[0].legend()

        axs[1].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['sum_soc_car'], label='agent')
        axs[1].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['sum_soc_car'], label='benchmark', color='black')
        axs[1].set_title('Sum of SOC (absolute) per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['sum_soc_car'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['sum_soc_car'].max()
        axs[1].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[1].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')
        #axs[1].legend()


        axs[2].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['number_of_charging_vehicles_car'].rolling(window=self.rolling_window).mean(), label='agent')
        axs[2].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_charging_vehicles_car'], label='benchmark', color='black')
        axs[2].set_title('Number of charging vehicles per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_charging_vehicles_car'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_charging_vehicles_car'].max()
        axs[2].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[2].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')

        axs[3].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['maximum_queue_length_cars'].rolling(window=self.rolling_window).mean(), label='agent')
        axs[3].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['maximum_queue_length_cars'], label='benchmark', color='black')
        axs[3].set_title('Maximum number of waiting cars for charging per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['maximum_queue_length_cars'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['maximum_queue_length_cars'].max()
        axs[3].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[3].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')
        axs[3].legend(loc='upper center', bbox_to_anchor=(0.5,-0.15), ncol=2)


        plt.savefig(os.path.join(self.folder_name, 'episodic_progress_charging_kpis_car.png'))
        plt.show()

        ############################ charging kpis scooters ################################################################
        fig, axs = plt.subplots(4, 1, constrained_layout=True, figsize=(10,8))

        fig.suptitle("Scooter KPIs", fontsize=16, fontweight='bold')

        axs[0].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['number_of_vehicles_below_critical_soc_treshold_scooter'],
                    label='agent')
        axs[0].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_vehicles_below_critical_soc_treshold_scooter'], label='benchmark', color='black')

        axs[0].set_title('Number of vehicles below critical threshold per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0][
            'number_of_vehicles_below_critical_soc_treshold_scooter'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0][
            'number_of_vehicles_below_critical_soc_treshold_scooter'].max()
        axs[0].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[0].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')
        #axs[0].legend()

        axs[1].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['sum_soc_scooter'], label='agent')
        axs[1].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['sum_soc_scooter'], label='benchmark', color='black')
        axs[1].set_title('Sum of SOC (absolute) per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['sum_soc_scooter'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['sum_soc_scooter'].max()
        axs[1].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[1].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')
        #axs[1].legend()

        axs[2].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['number_of_charging_vehicles_scooter'].rolling(window=self.rolling_window).mean(),
                    label='agent')
        axs[2].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_charging_vehicles_scooter'], label='benchmark', color='black')

        axs[2].set_title('Number of charging vehicles per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_charging_vehicles_scooter'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_charging_vehicles_scooter'].max()
        axs[2].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[2].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')

        axs[3].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['maximum_queue_length_scooters'].rolling(window=self.rolling_window).mean(), label='agent')
        axs[3].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['maximum_queue_length_scooters'], label='benchmark', color='black')
        axs[3].set_title('Maximum number of waiting scooters for charging per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['maximum_queue_length_scooters'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['maximum_queue_length_scooters'].max()
        axs[3].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[3].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')
        axs[3].legend(loc='upper center', bbox_to_anchor=(0.5,-0.15), ncol=2)

        plt.savefig(os.path.join(self.folder_name, 'episodic_progress_charging_kpis_scooter.png'))
        plt.show()

        ############################ charging kpis kickscooter ################################################################
        fig, axs = plt.subplots(4, 1, constrained_layout=True, figsize=(10,8))
        fig.suptitle("Kickscooter KPIs", fontsize=16, fontweight='bold')

        axs[0].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0][
                        'number_of_vehicles_below_critical_soc_treshold_kickscooter'],
                    label='agent')
        axs[0].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0][
                        'number_of_vehicles_below_critical_soc_treshold_kickscooter'], label='benchmark', color='black')

        axs[0].set_title('Number of vehicles below critical threshold per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0][
            'number_of_vehicles_below_critical_soc_treshold_kickscooter'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0][
            'number_of_vehicles_below_critical_soc_treshold_kickscooter'].max()
        axs[0].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[0].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')
        #axs[0].legend()

        axs[1].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['sum_soc_kickscooter'],
                    label='agent')
        axs[1].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['sum_soc_kickscooter'],
                    label='benchmark', color='black')

        axs[1].set_title('Sum of SOC (absolute) per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['sum_soc_kickscooter'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['sum_soc_kickscooter'].max()
        axs[1].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[1].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')
        #axs[1].legend()

        axs[2].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0][
                        'number_of_charging_vehicles_kickscooter'].rolling(window=self.rolling_window).mean(),
                    label='agent')
        axs[2].plot(
            self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['number_of_charging_vehicles_kickscooter'],
            label='benchmark', color='black')

        axs[2].set_title('Number of charging vehicles per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0][
            'number_of_charging_vehicles_kickscooter'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0][
            'number_of_charging_vehicles_kickscooter'].max()
        axs[2].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[2].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')

        axs[3].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['maximum_queue_length_kickscooters'].rolling(window=self.rolling_window).mean(), label='agent')
        axs[3].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['maximum_queue_length_kickscooters'], label='benchmark', color='black')
        axs[3].set_title('Maximum number of waiting kickscooters for charging per hour')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['maximum_queue_length_kickscooters'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['maximum_queue_length_kickscooters'].max()
        axs[3].axhline(y=min, color='r', linestyle='-', label='minimum benchmark value')
        axs[3].axhline(y=max, color='r', linestyle='-', label='maximum benchmark value')
        axs[3].legend(loc='upper center', bbox_to_anchor=(0.5,-0.15), ncol=2)


        plt.savefig(os.path.join(self.folder_name, 'episodic_progress_charging_kpis_kickscooter.png'))
        plt.show()


        #################################### agent rewards ###############################################################
        fig, axs = plt.subplots(3, 1, constrained_layout=True, figsize=(10,8))

        fig.suptitle("Average reward per action", fontsize=16, fontweight='bold')

        axs[0].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]["avg_car_agent_reward_sum"].rolling(window=100).mean(), label='avg_car_agent_reward_sum')
        axs[0].set_title('Cars')

        axs[1].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['avg_scooter_agent_reward_sum'].rolling(window=100).mean(), label='avg_scooter_agent_reward_sum')
        axs[1].set_title('Scooters')

        axs[2].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['avg_kickscooter_agent_reward_sum'].rolling(window=100).mean(), label='avg_kickscooter_agent_reward_sum')
        axs[2].set_title('Kickscooters')

        plt.savefig(os.path.join(self.folder_name, 'episodic_progress_agent_reward.png'))

        plt.show()

        ########################################### charging amounts ##############################################
        fig, axs = plt.subplots(3, 1, constrained_layout=True, figsize=(10,8))
        fig.suptitle("Charging Amount (Kwh) per hour", fontsize=16, fontweight='bold')

        axs[0].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['car_charging_sum'].rolling(window=self.rolling_window).mean(), label='agent')
        axs[0].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['car_charging_sum'].rolling(window=self.rolling_window).mean(), label='benchmark', color='black')
        axs[0].set_title('Cars')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['car_charging_sum'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['car_charging_sum'].max()
        axs[0].axhline(y=min, color='r', linestyle='-', label='min value from benchmark algorithm')
        axs[0].axhline(y=max, color='r', linestyle='-', label='max value from benchmark algorithm')
        # axs[0].legend()

        axs[1].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['scooter_charging_sum'].rolling(window=self.rolling_window).mean(), label='agent')
        axs[1].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['scooter_charging_sum'].rolling(window=self.rolling_window).mean(), label='benchmark', color='black')
        axs[1].set_title('Scooters')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['scooter_charging_sum'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['scooter_charging_sum'].max()
        axs[1].axhline(y=min, color='r', linestyle='-', label='min value from benchmark algorithm')
        axs[1].axhline(y=max, color='r', linestyle='-', label='max value from benchmark algorithm')
        # axs[1].legend()


        axs[2].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] != 0]['kickscooter_charging_sum'].rolling(window=self.rolling_window).mean(), label='agent')
        axs[2].plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['kickscooter_charging_sum'].rolling(window=self.rolling_window).mean(), label='benchmark', color='black')
        axs[2].set_title('Kickscooters')
        min = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['kickscooter_charging_sum'].min()
        max = self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0]['kickscooter_charging_sum'].max()
        axs[2].axhline(y=min, color='r', linestyle='-', label='min value from benchmark algorithm')
        axs[2].axhline(y=max, color='r', linestyle='-', label='max value from benchmark algorithm')
        axs[2].legend(loc='upper center', bbox_to_anchor=(0.5,-0.15), ncol=2)

        plt.savefig(os.path.join(self.folder_name, 'episodic_progress_charging_amounts.png'))
        plt.show()

        ########################################## service level, revenue #############################################
        fig, axs = plt.subplots(4, 1, constrained_layout=True, figsize=(10,8))

        fig.suptitle("Operator KPIs", fontsize=16, fontweight='bold')

        axs[0].plot(self.simulation_results['total_fulfilled_trips'].iloc[1:], label='total_fulfilled_trips')

        axs[0].set_title('Total fulfilled trips per episode')
        axs[0].axhline(y=self.simulation_results['total_fulfilled_trips'].iloc[0], color='r', linestyle='-')

        axs[1].plot(self.simulation_results['total_missed_trips'].iloc[1:], label='total_missed_trips')
        axs[1].set_title('Total missed trips per episode')
        axs[1].axhline(y=self.simulation_results['total_missed_trips'].iloc[0], color='r', linestyle='-')

        self.simulation_results['alpha_service_level'] = 1 - (self.simulation_results['total_missed_trips'] / (
                    self.simulation_results['total_fulfilled_trips'] + self.simulation_results['total_missed_trips']))
        axs[2].plot(self.simulation_results['alpha_service_level'].iloc[1:], label='alpha_service_level')
        axs[2].set_title('Service Level per episode')
        axs[2].axhline(y=self.simulation_results['alpha_service_level'].iloc[0], color='r', linestyle='-')

        axs[3].plot(self.simulation_results['total_revenue'].iloc[1:], label='total_revenue')
        axs[3].set_title('Total revenue per episode')
        axs[3].axhline(y=self.simulation_results['total_revenue'].iloc[0], color='r', linestyle='-')

        plt.savefig(os.path.join(self.folder_name, 'episodic_progress_service_level.png'))
        plt.show()

    def plot_agent_results(self):

        # cars
        plt.plot(self.agent_results_car['executed_actions'], self.agent_results_car['policy_loss'].rolling(window=100).mean(), label='policy_loss')
        plt.title('policy_loss_cars')
        plt.xlabel('Executed Actions')
        plt.savefig(os.path.join(self.folder_name, 'policy_loss_cars.png'))
        plt.show()

        plt.plot(self.agent_results_car['executed_actions'], self.agent_results_car['reward [0]'].rolling(window=100).mean(), label='reward [0]')
        plt.title('reward [0] cars')
        plt.xlabel('Executed Actions')
        plt.savefig(os.path.join(self.folder_name, 'reward_[0]_cars.png'))
        plt.show()

        plt.plot(self.agent_results_car['executed_actions'], self.agent_results_car['epsilon'].rolling(window=self.rolling_window).mean(), label='epsilon')
        plt.title('epsilon cars')
        plt.xlabel('Executed Actions')
        plt.savefig(os.path.join(self.folder_name, 'epsilon_cars.png'))
        plt.show()

        # scooters
        plt.plot(self.agent_results_scooter['executed_actions'], self.agent_results_scooter['policy_loss'].rolling(window=100).mean(), label='policy_loss')
        plt.title('policy_loss_scooters')
        plt.xlabel('Executed Actions')
        plt.savefig(os.path.join(self.folder_name, 'policy_loss_scooters.png'))
        plt.show()

        plt.plot(self.agent_results_scooter['executed_actions'], self.agent_results_scooter['reward [0]'].rolling(window=100).mean(), label='reward [0]')
        plt.title('reward [0] scooters')
        plt.xlabel('Executed Actions')
        plt.savefig(os.path.join(self.folder_name, 'reward_[0]_scooters.png'))
        plt.show()

        plt.plot(self.agent_results_scooter['executed_actions'], self.agent_results_scooter['epsilon'].rolling(window=self.rolling_window).mean(), label='epsilon')
        plt.title('epsilon scooters')
        plt.xlabel('Executed Actions')
        plt.savefig(os.path.join(self.folder_name, 'epsilon_scooters.png'))
        plt.show()

        # kickscooters
        plt.plot(self.agent_results_kickscooter['executed_actions'], self.agent_results_kickscooter['policy_loss'].rolling(window=100).mean(), label='policy_loss')
        plt.title('policy_loss_kickscooters')
        plt.xlabel('Executed Actions')
        plt.savefig(os.path.join(self.folder_name, 'policy_loss_kickscooters.png'))
        plt.show()

        plt.plot(self.agent_results_kickscooter['executed_actions'], self.agent_results_kickscooter['reward [0]'].rolling(window=100).mean(), label='reward [0]')
        plt.title('reward [0] kickscooters')
        plt.xlabel('Executed Actions')
        plt.savefig(os.path.join(self.folder_name, 'reward_[0]_kickscooters.png'))
        plt.show()

        plt.plot(self.agent_results_kickscooter['executed_actions'], self.agent_results_kickscooter['epsilon'].rolling(window=self.rolling_window).mean(), label='epsilon')
        plt.title('epsilon kickscooters')
        plt.xlabel('Executed Actions')
        plt.savefig(os.path.join(self.folder_name, 'epsilon_kickscooters.png'))
        plt.show()

    def plot_vehicles_below_soc_over_time(self):

        plt.plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0] \
                 ['number_of_vehicles_below_critical_soc_treshold_car'] / self._number_cars*100,
                 label='Cars')
        plt.plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0] \
                 ['number_of_vehicles_below_critical_soc_treshold_scooter'] / self._number_scooters*100,
                 label='Scooters')
        plt.plot(self.kpi_tracker_results[self.kpi_tracker_results['episode'] == 0] \
                 ['number_of_vehicles_below_critical_soc_treshold_kickscooter'] / self._number_kickscooters*100,
                 label='Kickscooters')

        plt.legend()
        plt.ylabel("Proportion (%)")
        plt.title('Vehicles below Critical SOC')
        plt.show()

    def print_average_idle_time_per_vehicle_type(self, use_last_episode):
        """
        if use_last_episode == False, use first episode
        :param use_last_episode:
        :return:
        """
        idx = 0 if use_last_episode == False else -1

        idle_time_car = self.simulation_results['average_idle_time_per_car'].iloc[idx]
        print(f"Average time per car below critical threshold: {round(idle_time_car,2)} minutes ({round((idle_time_car/self.episode_duration)*100, 2)}%)")

        idle_time_scooter = self.simulation_results['average_idle_time_per_scooter'].iloc[idx]
        print(f"Average time per scooter below critical threshold: {round(idle_time_scooter,2)} minutes ({round((idle_time_scooter/self.episode_duration)*100, 2)}%)")

        idle_time_kickscooter = self.simulation_results['average_idle_time_per_kickscooter'].iloc[idx]
        print(f"Average time per kick scooter below critical threshold: {round(idle_time_kickscooter,2)} minutes ({round((idle_time_kickscooter/self.episode_duration)*100,2)}%)")


    def print_charging_relocation_distance_duration(self):

        print(f"Charging Relocation Duration: {round(self.simulation_results['charging_relocation_duration'].iloc[0]/60,2)} hours")
        print(f"Charging Relocation Duration Proportion: {round(self.simulation_results['charging_relocation_duration'].iloc[0]/(self.episode_duration*self._number_vehicles)*100,2)} %")
        print(f"Charging Relocation Distance: {round(self.simulation_results['charging_relocation_distance'].iloc[0]/1000,2)} km")



    def plot_agent_behaviour_and_charging_stations(self, agent_type, origin):
        """
        :param df: Df conaining time_bucket, hexagon_id and feature
        :param geojson_obj: Geojson object containing hexagon_id properties and polygons
        :param feature: Feature to color hexagons
        :return:
        """

        if agent_type == 'SharedCar':
            df = self.car_agent_behaviour
        elif agent_type == 'SharedScooter':
            df = self.scooter_agent_behaviour
        elif agent_type == 'SharedKickScooter':
            df = self.kickscooter_agent_behaviour
        else:
            df = pd.DataFrame()

        df["charging_station"] = df.apply(lambda x: 1 if x["Unnamed: 0"] in self.charging_stations else 0, axis=1)

        fig = (px.choropleth_mapbox(
            df,
            geojson=self.geojson_obj,
            locations='Unnamed: 0',
            featureidkey=f'properties.hex_id_{self.spatial_res}',
            color=origin,
            color_continuous_scale='Reds',
            mapbox_style='carto-positron',
            hover_data=[origin, "charging_station"],
            range_color=(0, 1),
            zoom=9,
            center={"lat": 52.52, "lon": 13.381}
        ))
        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
        fig.write_html(os.path.join(self.folder_name, f'{agent_type}_agent_behaviour.html'), auto_open=True)

        # plot charging stations
        fig = (px.choropleth_mapbox(
            df,
            geojson=self.geojson_obj,
            locations='Unnamed: 0',
            featureidkey=f'properties.hex_id_{self.spatial_res}',
            color="charging_station",
            color_continuous_scale='Greens',
            mapbox_style='carto-positron',
            hover_data=[origin, "charging_station"],
            range_color=(0, 1),
            zoom=9,
            center={"lat": 52.52, "lon": 13.381}
        ))
        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
        fig.write_html(os.path.join(self.folder_name, f'{agent_type}_charging_stations.html'), auto_open=True)

    def save_params(self):

        ini_file_path = os.path.join(f"resources\\configurations\\app-local.ini")
        main_file_path = os.path.join(f"main_charging.py")

        shutil.copy(ini_file_path, os.path.join(self.folder_name, 'app-local.ini'))
        shutil.copy(main_file_path, os.path.join(self.folder_name, 'main_charging.py'))

    def numerical_assessment_calculate_descriptions(self):

        df_grouped = self.kpi_tracker_results.groupby('episode').agg({'number_of_vehicles_below_critical_soc_treshold_car': 'max',
                                                                      'number_of_vehicles_below_critical_soc_treshold_scooter': 'max',
                                                                      'number_of_vehicles_below_critical_soc_treshold_kickscooter': 'max',
                                                                      'sum_soc_car': 'min',
                                                                      'sum_soc_scooter': 'min',
                                                                      'sum_soc_kickscooter': 'min'})


        ######################################## Vehicles below critical SCO ###########################################
        start_vehicles_below_critical_soc_cars = df_grouped['number_of_vehicles_below_critical_soc_treshold_car'][1:2].mean()
        end_vehicles_below_critical_soc_cars = df_grouped['number_of_vehicles_below_critical_soc_treshold_car'][-4:-1].mean()
        improvement_vehicles_below_critical_soc_cars = 1 - (end_vehicles_below_critical_soc_cars/start_vehicles_below_critical_soc_cars)

        start_vehicles_below_critical_soc_scooters = df_grouped['number_of_vehicles_below_critical_soc_treshold_scooter'][1:2].mean()
        end_vehicles_below_critical_soc_scooters = df_grouped['number_of_vehicles_below_critical_soc_treshold_scooter'][-4:-1].mean()
        improvement_vehicles_below_critical_soc_scooters = 1 - (end_vehicles_below_critical_soc_scooters/start_vehicles_below_critical_soc_scooters)
        
        start_vehicles_below_critical_soc_kickscooters = df_grouped['number_of_vehicles_below_critical_soc_treshold_kickscooter'][1:2].mean()
        end_vehicles_below_critical_soc_kickscooters = df_grouped['number_of_vehicles_below_critical_soc_treshold_kickscooter'][-4:-1].mean()
        improvement_vehicles_below_critical_soc_kickscooters = 1 - (end_vehicles_below_critical_soc_kickscooters/start_vehicles_below_critical_soc_kickscooters)


        ######################################## SUM SOC ###########################################
        start_sum_soc_cars = (df_grouped['sum_soc_car'][1:2]/16.7/self._number_cars).mean()
        end_sum_soc_cars = (df_grouped['sum_soc_car'][-4:-1]/16.7/self._number_cars).mean()
        improvement_sum_soc_cars = (end_sum_soc_cars-start_sum_soc_cars) / start_sum_soc_cars
        
        start_sum_soc_scooters = (df_grouped['sum_soc_scooter'][1:2]/4.8/self._number_scooters).mean()
        end_sum_soc_scooters = (df_grouped['sum_soc_scooter'][-4:-1]/4.8/self._number_scooters).mean()
        improvement_sum_soc_scooters = (end_sum_soc_scooters-start_sum_soc_scooters) / start_sum_soc_scooters
        
        start_sum_soc_kickscooters = (df_grouped['sum_soc_kickscooter'][1:2]/0.288/self._number_kickscooters).mean()
        end_sum_soc_kickscooters = (df_grouped['sum_soc_kickscooter'][-4:-1]/0.288/self._number_kickscooters).mean()
        improvement_sum_soc_kickscooters = (end_sum_soc_kickscooters-start_sum_soc_kickscooters) / start_sum_soc_kickscooters
        
        result_string_cars = f"Cars: \n start vehicles below critical SOC: {start_vehicles_below_critical_soc_cars} \n " \
                        f"end vehicles below critical SOC: {end_vehicles_below_critical_soc_cars} \n" \
                        f"improvement critical SOC: {improvement_vehicles_below_critical_soc_cars} \n" \
                        f"start sum soc:  {start_sum_soc_cars} \n" \
                        f"end sum soc: {end_sum_soc_cars} \n" \
                        f"improvement sum soc: {improvement_sum_soc_cars} \n \n \n"
        
        result_string_scooters = f"Scooters: \n start vehicles below critical SOC: {start_vehicles_below_critical_soc_scooters} \n " \
                        f"end vehicles below critical SOC: {end_vehicles_below_critical_soc_scooters} \n" \
                        f"improvement critical SOC: {improvement_vehicles_below_critical_soc_scooters} \n" \
                        f"start sum soc:  {start_sum_soc_scooters} \n" \
                        f"end sum soc: {end_sum_soc_scooters} \n" \
                        f"improvement sum soc: {improvement_sum_soc_scooters} \n \n \n"
        
        result_string_kickscooters = f"Kickscooters: \n start vehicles below critical SOC: {start_vehicles_below_critical_soc_kickscooters} \n " \
                        f"end vehicles below critical SOC: {end_vehicles_below_critical_soc_kickscooters} \n" \
                        f"improvement critical SOC: {improvement_vehicles_below_critical_soc_kickscooters} \n" \
                        f"start sum soc:  {start_sum_soc_kickscooters} \n" \
                        f"end sum soc: {end_sum_soc_kickscooters} \n" \
                        f"improvement sum soc: {improvement_sum_soc_kickscooters} \n \n \n"


        ############################################ OPERATOR KPIS ################################################
        total_revenue_start = self.simulation_results['total_revenue'][1:2].mean()
        total_revenue_end = self.simulation_results['total_revenue'][-4:-1].mean()
        total_revenue_improvement = (total_revenue_end - total_revenue_start) / total_revenue_start

        missed_trips_start = self.simulation_results['total_missed_trips'][1:2].mean()
        missed_trips_end = self.simulation_results['total_missed_trips'][-4:-1].mean()
        missed_trips_improvment = (missed_trips_end - missed_trips_start) / missed_trips_start

        with open(self.numerical_assessment_file_path, 'w') as f:
            f.write(result_string_cars + "\n \n \n" + result_string_scooters + "\n \n \n" + result_string_kickscooters +
                    f"\n \n \n" + f"Operator KPIS: \n start revenue: {total_revenue_start} \n end revenue: {total_revenue_end} \n"
                                  f"improvement revenue: {total_revenue_improvement}, \n \n "
                                  f"start missed trips: {missed_trips_start} \n end missed trips: {missed_trips_end} \n "
                                  f"improvement missed trips: {missed_trips_improvment}")

    def thesis_results_q_value_convergence_bar_chart(self):

        # destination holds charging station
        fig, axs = plt.subplots(2, 1, constrained_layout=True, figsize=(10, 8))

        fig.suptitle("Q-Values for each Action if Destination provides a Charging Station", fontsize=16, fontweight='bold')

        relevant_car_columns = [column for column in self.agent_results_car.columns if 'with_charging' in column]

        data = self.agent_results_car.iloc[-2][relevant_car_columns]

        data = data.reset_index()
        data_normalizer = mp.colors.Normalize()
        color_map = mp.colors.LinearSegmentedColormap(
            "my_map",
            {
                "red": [(0, 1.0, 1.0),
                        (1.0, .5, .5)],
                "green": [(0, 0.5, 0.5),
                          (1.0, 0, 0)],
                "blue": [(0, 0.50, 0.5),
                         (1.0, 0, 0)]
            }
        )
        axs[0].bar(data.index, data.iloc[:,1], color=color_map(data_normalizer(data.iloc[:,1])))
        axs[0].set_xticks(data.index)

        #axs[0].set_xlabel('Actions')
        axs[0].set_ylabel('Q-Value')
        axs[0].set_title('Car Agent')

        # scooter
        relevant_scooter_columns = [column for column in self.agent_results_scooter.columns if 'with_charging' in column]

        data_scooter = self.agent_results_scooter.iloc[-2][relevant_scooter_columns]

        data_scooter = data_scooter.reset_index()

        data_normalizer_scooter = mp.colors.Normalize()
        color_map_scooter = mp.colors.LinearSegmentedColormap(
            "my_map",
            {
                "red": [(0, 1.0, 1.0),
                        (1.0, .5, .5)],
                "green": [(0, 0.5, 0.5),
                          (1.0, 0, 0)],
                "blue": [(0, 0.50, 0.5),
                         (1.0, 0, 0)]
            }
        )

        axs[1].bar(data_scooter.index, data_scooter.iloc[:,1], color=color_map_scooter(data_normalizer_scooter(data_scooter.iloc[:,1])))
        axs[1].set_xticks(data_scooter.index)

        axs[1].set_xlabel('Actions')
        axs[1].set_ylabel('Q-Value')
        axs[1].set_title('Scooter Agent')
        plt.savefig(os.path.join(self.folder_name, 'q_values_without_charging_station.png'))
        fig.show()

if __name__ == "__main__":

    import datetime
    import shutil

    # Change working directory to path of main.py
    working_dir = Path(__file__).parent.parent.parent
    print(working_dir)
    os.chdir(working_dir)

    now = datetime.datetime.now()

    folder_name = f'C:\\Users\\Fabian Weiland\\OneDrive\\Uni\\Information Systems Master\\4. Semester\\Results_Charging' \
                  f'\\0{now.month}_{now.day}_{now.hour}_' \
                  f'{now.minute}_{now.second}'\

    # Read args
    parser = ConfigParser()
    parser.read(sys.argv[1])

    temporal_res = 4# parser.getint("WORLD", "TEMPORAL_RESOLUTION")
    spatial_res = 8# parser.getint("WORLD", "SPATIAL_RESOLUTION")

    # episode = 1 --> last , episode = 2 --> second last
    episode = 1
    idx = 0
    rolling_window = 1
    kpi_tracker_service_worker_suffix = ""
    
    desc_object = DescriptiveAnalysis(temporal_res, spatial_res, episode, idx, folder_name, rolling_window, kpi_tracker_service_worker_suffix)
    #desc_object.sensitivity_analysis_demand_side()
    #desc_object.sensitivity_analysis_service_worker()
    desc_object.sensitivity_analysis_three_charging_strategies()

    #desc_object.episodic_progress()
    #desc_object.plot_agent_results()

    hex_7 = '871f1d49dffffff'
    hex_8 = '881f1d4899fffff'

    #desc_object.plot_agent_behaviour_and_charging_stations('SharedCar', hex_8)
    #desc_object.save_params()

    # desc_object.plot_vehicles_below_soc_over_time()
    # desc_object.print_average_idle_time_per_vehicle_type(use_last_episode=False)
    # desc_object.print_charging_relocation_distance_duration()
    #
    # desc_object.thesis_numerical_assessment_plots()
    #desc_object.thesis_results()
    # desc_object.numerical_assessment_calculate_descriptions()
    # desc_object.thesis_results_q_value_convergence_bar_chart()
    suffix = input("Please insert folder suffix:\n")
    os.rename(folder_name, f"{folder_name}_{suffix}")

    print(f"Results saved into folder: {folder_name}_{suffix}")