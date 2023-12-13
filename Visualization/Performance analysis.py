import datetime as dt
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import set_matplotlib_formats

def clean(x):
    if type(x) != float:
        x = x.replace('[', '').replace(']', '')
    return x

def set_style():
    # This sets reasonable defaults for font size for a figure that will go in a paper
    sns.set_context("paper")

    # Set the font to be serif, rather than sans
    sns.set(font='serif')
    # sns.set_color_codes("pastel")
    sns.set_palette("mako", n_colors=2)
    # Make the background white, and specify the font family
    sns.set_style("ticks", {
        "font.family": "serif",
        "font.serif": ["Times", "Palatino", "serif"]
    })


def data_preparation(df_raw):
    df_raw['phase'] += 1
    df_raw['total_profit_ride_hailing'] = df_raw['total_cost_per_day_ride_hailing'] + \
                                          df_raw['total_profit_ride_hailing']
    df_raw['waiting_time'] = df_raw['AutonomousCar_True_waiting_time'] + df_raw['RideHailingCar_True_waiting_time'] \
                             + df_raw['RideHailingCar_False_waiting_time']
    df_raw['pick_up_time'] = df_raw['AutonomousCar_True_pick_up_time'] + df_raw['RideHailingCar_True_pick_up_time'] + \
                             df_raw['RideHailingCar_False_pick_up_time']
    df_raw['total_waiting_time'] = (df_raw['waiting_time'] +
                                    df_raw['pick_up_time'])/df_raw['total_fulfilled_trips_ride_hailing']
    df_raw['service_quality'] = (df_raw['total_fulfilled_trips_ride_hailing']) / 7600


    return df_raw

def plot_CS_Benchmark(dg):
    set_style()
    fig, ax = plt.subplots(nrows=1, ncols=4, figsize=(12, 4),constrained_layout=True)
    HUE= 'scenario'
    N_COLORS = 5
    DODGE = True
    X = 'phase'
    X_LABLE = 'Technology Phases'
    Y = ['total_profit_ride_hailing','total_operational_cost_per_day_ride_hailing', 'service_quality', 'total_waiting_time']
    Y_LABLE = ['Profits($)', 'Costs($)', 'Served Requests(%)', 'Time(minute)']
    Title = ['Fleet Profits', 'Fleet Costs', 'Service Quality', 'Waiting Time']
    Y_LIMIT_UP = [95000, 24000, 1.1, 12]
    Y_LIMIT_LO = [30000, 5000, 6500]
    # for i in range(5):
    #     for j in range(3):
    #         sns.boxplot(data=dg[i], x=X, y=Y[j], hue=HUE, palette=sns.color_palette('mako', n_colors=N_COLORS), ax=ax[i][j],
    #                     dodge=DODGE)
    #         ax[i][j].set_ylim(Y_LIMIT_LO[j], Y_LIMIT_UP[j])
    #         ax[i][j].set_xlabel(X_LABLE, fontsize=12)
    #         ax[i][j].set_ylabel(Y_LABLE[j]+'s',fontsize=12)
    #         ax[i][j].set_title(Title[j], fontsize=12)
    #         ax[i][j].tick_params(axis='both', labelsize=8)
    for i in range(4):
        sns.barplot(data=dg, x=X, y=Y[i], hue=HUE, palette=sns.color_palette('mako', n_colors=N_COLORS), ax=ax[i],
                    dodge=DODGE)
        ax[i].set_ylim(0, Y_LIMIT_UP[i])
        ax[i].set_xlabel(X_LABLE, fontsize=12)
        ax[i].set_ylabel(Y_LABLE[i],fontsize=12)
        ax[i].set_title(Title[i], fontsize=12)
        ax[i].tick_params(axis='both', labelsize=12)

    plt.savefig("/home/rahadi/Projects/urban-mobility-simulation/data/output/revenue.pdf")
    plt.show()


def plot_CS_Benchmark_new(dg):
    set_style()
    fig, ax = plt.subplots(nrows=1, ncols=2, figsize=(12, 4),constrained_layout=True)
    HUE= 'scenario'
    N_COLORS = 5
    DODGE = True
    X = 'phase'
    X_LABLE = 'Technology Phases'
    Y = ['total_profit_ride_hailing','total_profit_ride_hailing', 'service_quality', 'total_waiting_time']
    Y_LABLE = ['Profits($)', 'Profits($)', 'Served Requests(%)', 'Time(minute)']
    Title = ['Fleet Profits with Two Vehicle Options', 'Fleet Profits with One Vehicle Option', 'Service Quality', 'Waiting Time']
    Y_LIMIT_UP = [85000, 24000, 8000]
    Y_LIMIT_LO = [30000, 5000, 6500]
    # for i in range(5):
    #     for j in range(3):
    #         sns.boxplot(data=dg[i], x=X, y=Y[j], hue=HUE, palette=sns.color_palette('mako', n_colors=N_COLORS), ax=ax[i][j],
    #                     dodge=DODGE)
    #         ax[i][j].set_ylim(Y_LIMIT_LO[j], Y_LIMIT_UP[j])
    #         ax[i][j].set_xlabel(X_LABLE, fontsize=12)
    #         ax[i][j].set_ylabel(Y_LABLE[j]+'s',fontsize=12)
    #         ax[i][j].set_title(Title[j], fontsize=12)
    #         ax[i][j].tick_params(axis='both', labelsize=8)
    for i in range(2):
        sns.barplot(data=dg[i], x=X, y=Y[i], hue=HUE, palette=sns.color_palette('mako', n_colors=N_COLORS), ax=ax[i],
                    dodge=DODGE)
        # ax[i].set_ylim(0, 105)
        ax[i].set_xlabel(X_LABLE, fontsize=12)
        ax[i].set_ylabel(Y_LABLE[i],fontsize=12)
        ax[i].set_title(Title[i], fontsize=12)
        ax[i].tick_params(axis='both', labelsize=12)

    plt.savefig("/home/rahadi/Projects/urban-mobility-simulation/data/output/revenue.pdf")
    plt.show()

df_raw_results = pd.DataFrame()
for i in range(5):
    base_path = f'/home/rahadi/Projects/urban-mobility-simulation/data/output/scenario_{i+1}_250_all_simulation_results.csv'
    new_df = pd.read_csv(base_path)
    new_df['scenario'] = f'{i+1}'
    df_raw_results = pd.concat([df_raw_results,new_df], axis=0)
dg = data_preparation(df_raw_results)
print(dg.groupby(['phase', 'scenario']).agg({'service_quality':'mean'}))
plot_CS_Benchmark(dg)



# dg={}
# df_raw_results = pd.DataFrame()
# for i in range(5):
#     base_path = f'/home/rahadi/Projects/urban-mobility-simulation/data/output/scenario_{i+6}_500_no_alternative_all_simulation_results.csv'
#     new_df = pd.read_csv(base_path)
#     new_df['scenario'] = f'{i+6}'
#     df_raw_results = pd.concat([df_raw_results,new_df], axis=0)
#     # dg[i] = data_preparation(df_raw_results)
# dg[1] = data_preparation(df_raw_results)
# df_raw_results = pd.DataFrame()
# for i in range(5):
#     base_path = f'/home/rahadi/Projects/urban-mobility-simulation/data/output/scenario_{i+6}_500_all_simulation_results.csv'
#     new_df = pd.read_csv(base_path)
#     new_df['scenario'] = f'{i+6}'
#     df_raw_results = pd.concat([df_raw_results,new_df], axis=0)
#     # dg[i] = data_preparation(df_raw_results)
# dg[0] = data_preparation(df_raw_results)
# plot_CS_Benchmark_new(dg)