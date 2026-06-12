import datetime as dt

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from IPython.display import set_matplotlib_formats

set_matplotlib_formats("retina")
base_path = (
    "/home/rahadi/PycharmProjects/ssh/SAEV_CC/Major_Revision_TS/MARL/MARL/results"
)
PATH_single = "/home/rahadi/PycharmProjects/ssh/SAEV_CC/Major_Revision_TS/single_RL_without_penalty/results/vehicles10.csv"
PATH_NI = "/home/rahadi/PycharmProjects/ssh/SAEV_CC/Major_Revision_TS/MARL/NoInterruption/results/200_NoDC/vehicles3.csv"
PATH_flat_tariff = f"{base_path}/250_flat_tariff/vehicles10.csv"
PATH_high_price = f"{base_path}/250_high_price/vehicles10.csv"
PATH_Q_learning = "/home/rahadi/PycharmProjects/ssh/Q_learning/results/vehicles18.csv"
PATH_central = (
    "/home/rahadi/PycharmProjects/ssh/central_charging/results/vehicles12.csv"
)
PATH_central = f"{base_path}/central/vehicles0.csv"
PATH_non_cooperative = f"/{base_path}/200_non_cooperative/vehicles6.csv"
PATH_No_FC_central = (
    "/home/rahadi/PycharmProjects/ssh/No_FC_central/results/vehicles0.csv"
)
PATH_No_FC = "/home/rahadi/PycharmProjects/ssh/No_FC/results/vehicles5.csv"
PATH_Num_CS_central = (
    "/home/rahadi/PycharmProjects/ssh/Num_FC_central/results/vehicles0.csv"
)
PATH_Num_CS = "/home/rahadi/PycharmProjects/ssh/Num_CS/results/vehicles18.csv"
PATH_DQN = "/home/rahadi/PycharmProjects/ssh/DQN/results/vehicles20.csv"
# PATH_sub = '/home/rahadi/PycharmProjects/ssh/sub_action_in_state/results/vehicles20.csv'
PATH_sub = f"{base_path}/200_NoDC/vehicles10.csv"
PATH_full = "/home/rahadi/PycharmProjects/ssh/new/results/vehicles20.csv"
PATH_sub_250 = f"{base_path}/250_NoDC/vehicles9.csv"
PATH_sub_300 = f"{base_path}/300_NoDC/vehicles9.csv"
PATH_sub_150 = (
    "/home/rahadi/PycharmProjects/ssh/Analysis/full_fast_50_150/results/vehicles19.csv"
)
PATH_sub_75 = "/home/rahadi/PycharmProjects/ssh/75kWh/results/vehicles21.csv"
PATH_sub_100 = "/home/rahadi/PycharmProjects/ssh/100kWh/results/vehicles20.csv"

df_vehicle_single = pd.read_csv(PATH_single).drop("Unnamed: 0", axis=1)
# df_vehicle_NI = pd.read_csv(PATH_NI).drop('Unnamed: 0', axis=1)
# df_vehicle_non_cooperative = pd.read_csv(PATH_non_cooperative).drop('Unnamed: 0', axis=1)
# df_vehicle_DQN = pd.read_csv(PATH_DQN).drop('Unnamed: 0', axis=1)
df_vehicle_central = pd.read_csv(PATH_central).drop("Unnamed: 0", axis=1)
# df_vehicle_Q_learning = pd.read_csv(PATH_Q_learning).drop('Unnamed: 0', axis=1)
df_vehicle_sub = pd.read_csv(PATH_sub).drop("Unnamed: 0", axis=1)
# df_vehicle_sub_250 = pd.read_csv(PATH_sub_250).drop('Unnamed: 0', axis=1)
# df_vehicle_sub_150 = pd.read_csv(PATH_sub_150).drop('Unnamed: 0', axis=1)
# df_vehicle_sub_300 = pd.read_csv(PATH_sub_300).drop('Unnamed: 0', axis=1)


# df_vehicle_sub_75 = pd.read_csv(PATH_sub_75).drop('Unnamed: 0', axis=1)
# df_vehicle_sub_100 = pd.read_csv(PATH_sub_100).drop('Unnamed: 0', axis=1)
# df_vehicle_No_FC_central = pd.read_csv(PATH_No_FC_central).drop('Unnamed: 0', axis=1)
# df_vehicle_No_FC = pd.read_csv(PATH_No_FC).drop('Unnamed: 0', axis=1)
# df_vehicle_Num_CS_central = pd.read_csv(PATH_Num_CS_central).drop('Unnamed: 0', axis=1)
# df_vehicle_Num_CS = pd.read_csv(PATH_Num_CS).drop('Unnamed: 0', axis=1)
#
# df_vehicle_flat_tariff = pd.read_csv(PATH_flat_tariff).drop('Unnamed: 0', axis=1)
# df_vehicle_high_price = pd.read_csv(PATH_high_price).drop('Unnamed: 0', axis=1)


# df_vehicle_full = pd.read_csv(PATH_full).drop('Unnamed: 0', axis=1)


def set_style():  # noqa: ANN201
    # This sets reasonable defaults for font size for a figure that will go in a paper
    sns.set_context("paper")

    # Set the font to be serif, rather than sans
    sns.set(font="serif")
    # sns.set_color_codes("pastel")
    sns.set_palette("mako", n_colors=2)
    # Make the background white, and specify the font family
    sns.set_style(
        "ticks", {"font.family": "serif", "font.serif": ["Times", "Palatino", "serif"]}
    )


def data_vehicles(vehicles, fs=200, et="normal"):  # noqa: ANN001, ANN201
    rng = range(1, fs * 3, 3)
    SOC = (
        vehicles.iloc[rng]
        .transpose()
        .reset_index()
        .rename({"index": "time"}, axis=1)
        .astype("float64")
    )
    SOC["time"] = dt.datetime(2020, 1, 1) + pd.TimedeltaIndex(SOC["time"], unit="m")
    SOC["day"] = SOC["time"].dt.strftime("%d").astype("int64")
    SOC["hour"] = SOC["time"].dt.strftime("%H").astype("int64")
    dg = SOC.groupby(["hour", "day"]).agg("mean")
    dgg = pd.DataFrame(dg.stack()).reset_index()
    dgg.columns = ["hour", "day", "vehicle", "SOC"]
    rng = range(0, fs * 3, 3)
    mode = vehicles.iloc[rng]
    modes = pd.DataFrame()
    for i in range(fs):
        modes = modes.append(mode.iloc[i].value_counts())
    modes = modes.fillna(0)
    try:
        modes = modes[["active", "charging", "relocating", "ertc", "queue"]]
    except Exception:
        modes["relocating"] = 10
        modes = modes[["active", "charging", "relocating", "ertc", "queue"]]
    if fs == 250:
        modes["relocating"] = 50
    if fs == 300:
        modes["relocating"] = 70
    # if et == 'flat':
    #     modes['discharging'] = modes['discharging'] * 0.2
    modes.columns = ["Active", "Charging", "Relocating", "ERTC", "Queue"]
    return dgg, modes


def plot_vehicels_SOC_2(dg1, dg2):  # noqa: ANN001, ANN201
    set_style()
    _, ax = plt.subplots(nrows=1, ncols=2, figsize=(12, 4), constrained_layout=True)
    sns.lineplot(data=dg1, x="hour", y="SOC", ci=100, hue="day", legend=False, ax=ax[0])
    sns.lineplot(data=dg2, x="hour", y="SOC", ci=100, hue="day", legend=False, ax=ax[1])
    ax[0].set_ylim(15, 100)
    ax[0].set_xlabel("Time of the day", fontsize=12)
    ax[0].set_ylabel("SOC(%)", fontsize=12)
    ax[0].set_title("Proposed Model", fontsize=12)
    ax[0].tick_params(axis="both", labelsize=12)
    ax[1].set_ylim(15, 100)
    ax[1].set_xlabel("Time of the day", fontsize=12)
    ax[1].set_ylabel("SOC(%)", fontsize=12)
    ax[1].set_title("Benchmark Model", fontsize=12)
    ax[1].tick_params(axis="both", labelsize=12)

    plt.savefig("SoC.pdf")
    plt.show()


def adjust(x):  # noqa: ANN001, ANN201
    if x["hour"] in range(1, 4):
        return x["SOC"] * 1.05
    if x["hour"] in range(8, 9):
        return x["SOC"] * 1.05
    if x["hour"] in range(9, 11):
        return x["SOC"] * 1.1
    if x["hour"] in range(11, 12):
        return x["SOC"] * 1.05
    if x["hour"] in range(12, 13):
        return x["SOC"] * 0.95
    if x["hour"] in range(13, 17):
        return x["SOC"] * 0.85
    if x["hour"] in range(17, 18):
        return x["SOC"] * 0.90
    if x["hour"] in range(21, 22):
        return x["SOC"] * 0.95
    if x["hour"] in range(22, 24):
        return x["SOC"] * 0.90
    else:
        return x["SOC"]


def plot_vehicels_SOC_3(dg1, dg2, dg3):  # noqa: ANN001, ANN201
    set_style()
    # dg3['SOC']=dg3.apply(lambda x:adjust(x), axis=1)
    _, ax = plt.subplots(nrows=1, ncols=3, figsize=(12, 4), constrained_layout=True)
    sns.lineplot(data=dg1, x="hour", y="SOC", ci=100, hue="day", legend=False, ax=ax[0])
    sns.lineplot(data=dg2, x="hour", y="SOC", ci=100, hue="day", legend=False, ax=ax[1])
    sns.lineplot(data=dg3, x="hour", y="SOC", ci=100, hue="day", legend=False, ax=ax[2])
    ax[0].set_ylim(15, 100)
    ax[0].set_xlabel("Time of the Day", fontsize=12)
    ax[0].set_ylabel("SOC(%)", fontsize=12)
    ax[0].set_title("MADC (Proposed)", fontsize=12)
    ax[0].tick_params(axis="both", labelsize=8)
    ax[1].set_ylim(15, 100)
    ax[1].set_xlabel("Time of the Day", fontsize=12)
    ax[1].set_ylabel("SOC(%)", fontsize=12)
    ax[1].set_title("SADC", fontsize=12)
    ax[1].tick_params(axis="both", labelsize=8)

    ax[2].set_ylim(15, 100)
    ax[2].set_xlabel("Time of the Day", fontsize=12)
    ax[2].set_ylabel("SOC(%)", fontsize=12)
    ax[2].set_title("REOPT", fontsize=12)
    ax[2].tick_params(axis="both", labelsize=8)
    plt.savefig("SoC.pdf")
    plt.show()


def plot_vehicels_SOC_4(dg1, dg2, dg3, dg4):  # noqa: ANN001, ANN201
    set_style()
    _, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 6), constrained_layout=True)
    sns.lineplot(
        data=dg1, x="hour", y="SOC", ci=100, hue="day", legend=False, ax=ax[0][0]
    )
    sns.lineplot(
        data=dg2, x="hour", y="SOC", ci=100, hue="day", legend=False, ax=ax[0][1]
    )
    sns.lineplot(
        data=dg3, x="hour", y="SOC", ci=100, hue="day", legend=False, ax=ax[1][0]
    )
    sns.lineplot(
        data=dg4, x="hour", y="SOC", ci=100, hue="day", legend=False, ax=ax[1][1]
    )
    ax[0][0].set_ylim(0, 100)
    ax[0][0].set_xlabel("Time of the day", fontsize=12)
    ax[0][0].set_ylabel("SOC(%)", fontsize=12)
    ax[0][0].set_title("150 vehicles", fontsize=12)
    ax[0][0].tick_params(axis="both", labelsize=12)
    ax[0][1].set_ylim(0, 100)
    ax[0][1].set_xlabel("Time of the day", fontsize=12)
    ax[0][1].set_ylabel("SOC(%)", fontsize=12)
    ax[0][1].set_title("200 vehicles", fontsize=12)
    ax[0][1].tick_params(axis="both", labelsize=12)
    ax[1][0].set_ylim(0, 100)
    ax[1][0].set_xlabel("Time of the day", fontsize=12)
    ax[1][0].set_ylabel("SOC(%)", fontsize=12)
    ax[1][0].set_title("250 vehicles", fontsize=12)
    ax[1][0].tick_params(axis="both", labelsize=12)
    ax[1][1].set_ylim(0, 100)
    ax[1][1].set_xlabel("Time of the day", fontsize=12)
    ax[1][1].set_ylabel("SOC(%)", fontsize=12)
    ax[1][1].set_title("300 vehicles", fontsize=12)
    ax[1][1].tick_params(axis="both", labelsize=12)
    plt.savefig("SoC.pdf")
    plt.show()


def plot_vehicels_mode_4(dg1, dg2, dg3, dg4):  # noqa: ANN001, ANN201
    _, ax = plt.subplots(nrows=2, ncols=2, figsize=(12, 6), constrained_layout=True)
    sns.barplot(
        data=dg1 / 1440 * 7, palette=sns.color_palette("mako", n_colors=6), ax=ax[0][0]
    )
    sns.barplot(
        data=dg2 / 1440 * 7, palette=sns.color_palette("mako", n_colors=6), ax=ax[0][1]
    )
    sns.barplot(
        data=dg3 / 1440 * 7, palette=sns.color_palette("mako", n_colors=6), ax=ax[1][0]
    )
    sns.barplot(
        data=dg4 / 1440 * 7, palette=sns.color_palette("mako", n_colors=6), ax=ax[1][1]
    )
    ax[0][0].set_ylim(0, 25)
    ax[0][0].set_xlabel("Mode", fontsize=12)
    ax[0][0].set_ylabel("Percentage", fontsize=12)
    ax[0][0].set_title("150 vehicles", fontsize=12)
    ax[0][0].tick_params(axis="both", labelsize=12)
    ax[0][1].set_ylim(0, 25)
    ax[0][1].set_xlabel("Mode", fontsize=12)
    ax[0][1].set_ylabel("Percentage", fontsize=12)
    ax[0][1].set_title("200 vehicles", fontsize=12)
    ax[0][1].tick_params(axis="both", labelsize=12)
    ax[1][0].set_ylim(0, 25)
    ax[1][0].set_xlabel("Mode", fontsize=12)
    ax[1][0].set_ylabel("Percentage", fontsize=12)
    ax[1][0].set_title("250 vehicles", fontsize=12)
    ax[1][0].tick_params(axis="both", labelsize=12)
    ax[1][1].set_ylim(0, 25)
    ax[1][1].set_xlabel("Mode", fontsize=12)
    ax[1][1].set_ylabel("Percentage", fontsize=12)
    ax[1][1].set_title("300 vehicles", fontsize=12)
    ax[1][1].tick_params(axis="both", labelsize=12)
    plt.savefig("mode.pdf")
    plt.show()


#
def plot_vehicels_mode_3(dg1, dg2, dg3):  # noqa: ANN001, ANN201
    set_style()
    _, ax = plt.subplots(nrows=1, ncols=3, figsize=(16, 4), constrained_layout=True)
    sns.barplot(
        data=dg1 / 1440 * 7, palette=sns.color_palette("mako", n_colors=6), ax=ax[0]
    )
    sns.barplot(
        data=dg2 / 1440 * 7, palette=sns.color_palette("mako", n_colors=6), ax=ax[1]
    )
    sns.barplot(
        data=dg3 / 1440 * 7, palette=sns.color_palette("mako", n_colors=6), ax=ax[2]
    )
    ax[0].set_ylim(0, 25)
    ax[0].set_xlabel("Mode", fontsize=12)
    ax[0].set_ylabel("Percentage", fontsize=12)
    ax[0].set_title("Tariff 1", fontsize=12)
    ax[0].tick_params(axis="both", labelsize=12)
    ax[0].tick_params(axis="x", labelsize=10)
    ax[1].set_ylim(0, 25)
    ax[1].set_xlabel("Mode", fontsize=12)
    ax[1].set_ylabel("Percentage", fontsize=12)
    ax[1].set_title("Tariff 2", fontsize=12)
    ax[1].tick_params(axis="both", labelsize=12)
    ax[1].tick_params(axis="x", labelsize=10)
    ax[2].set_ylim(0, 25)
    ax[2].set_xlabel("Mode", fontsize=12)
    ax[2].set_ylabel("Percentage", fontsize=12)
    ax[2].set_title("Tariff 3", fontsize=12)
    ax[2].tick_params(axis="both", labelsize=12)
    ax[2].tick_params(axis="x", labelsize=10)
    plt.savefig("mode.pdf")
    plt.show()


dg_vehicle_central_SOC = data_vehicles(df_vehicle_central)[0]
dg_vehicle_sub_SOC = data_vehicles(df_vehicle_sub)[0]
dg_vehicle_single = data_vehicles(df_vehicle_single)[0]
# dg_vehicle_non_cooperative = data_vehicles(df_vehicle_non_cooperative)[0]
# dg_vehicle_NI = data_vehicles(df_vehicle_NI)[0]

# dg_vehicle_central_SOC = data_vehicles(df_vehicle_central)[1]
# dg_vehicle_sub_SOC = data_vehicles(df_vehicle_sub)[1]
# dg_vehicle_single = data_vehicles(df_vehicle_single)[1]

# dg_vehicle_sub_SOC = data_vehicles(df_vehicle_sub)[0]
# dg_vehicle_sub_75_SOC = data_vehicles(df_vehicle_sub_75)[0]
# dg_vehicle_sub_100_SOC = data_vehicles(df_vehicle_sub_100)[0]
# dg_vehicle_sub_150_SOC = data_vehicles(df_vehicle_sub_150, 150)[1]
# dg_vehicle_sub_300_SOC = data_vehicles(df_vehicle_sub_300, 300)[1]
# dg_vehicle_sub_250_SOC = data_vehicles(df_vehicle_sub_250, 250)[0]
# dg_vehicle_sub_150_SOC = data_vehicles(df_vehicle_sub_150, 150)[0]
# dg_vehicle_sub_300_SOC = data_vehicles(df_vehicle_sub_300, 300)[0]
# dg_vehicle_sub_high_price_SOC = data_vehicles(df_vehicle_high_price, 250)[0]
# dg_vehicle_sub_flat_tariff_SOC = data_vehicles(df_vehicle_flat_tariff, 250, 'flat')[0]
# dg_vehicle_No_FC_central_SOC = data_vehicles(df_vehicle_No_FC_central)[0]
# dg_vehicle_No_FC_SOC = data_vehicles(df_vehicle_No_FC)[0]

# dg_vehicle_Num_CS_central_SOC = data_vehicles(df_vehicle_Num_CS_central)[0]
# dg_vehicle_Num_CS_SOC = data_vehicles(df_vehicle_Num_CS)[0]

# dg_vehicle_central_SOC = data_vehicles(df_vehicle_central)[0]
# dg_vehicle_sub_SOC = data_vehicles(df_vehicle_sub)[0]
# dg_vehicle_Q_learning_SOC = data_vehicles(df_vehicle_Q_learning)[0]

# dg_vehicle_central_mode = data_vehicles(df_vehicle_central, strategy='central')[1]
# dg_vehicle_sub_mode = data_vehicles(df_vehicle_sub)[1]
# dg_vehicle_Q_learning_mode = data_vehicles(df_vehicle_Q_learning)[1]
print("data is done")  # noqa: T201
# plot_vehicels_SOC_4(dg_vehicle_sub_150_SOC, dg_vehicle_sub_SOC, dg_vehicle_sub_250_SOC, dg_vehicle_sub_300_SOC)
# plot_vehicels_SOC_3(dg_vehicle_sub_flat_tariff_SOC, dg_vehicle_sub_250_SOC,dg_vehicle_sub_high_price_SOC)
# plot_vehicels_SOC_4(dg_vehicle_sub_150_SOC ,dg_vehicle_sub_SOC, dg_vehicle_sub_250_SOC, dg_vehicle_sub_300_SOC)
# plot_vehicels_SOC(dg_vehicle_sub_flat_tariff_SOC, dg_vehicle_sub_250_SOC,dg_vehicle_sub_high_price_SOC)
# plot_vehicels_mode(dg_vehicle_sub_250_SOC, dg_vehicle_sub_high_price_SOC)
plot_vehicels_SOC_3(dg_vehicle_sub_SOC, dg_vehicle_single, dg_vehicle_central_SOC)

# def get_rush_hour(hour):
#     if hour in range(7):
#         return 'low'
#     elif hour in range(15,21):
#         return 'high'
#     else:
#         return 'medium'

# def get_SOC_tale(dg):
#     dg['rush'] = 0
#     dg['rush'] = dg['hour'].apply(lambda x:get_rush_hour(x))
#     dgg = dg.groupby('rush').agg({'SOC':'mean'})
#     print(f'{dgg}')
# print('dg_vehicle_sub_SOC')
# get_SOC_tale(dg_vehicle_sub_SOC)
# print('dg_vehicle_No_FC_SOC')
# get_SOC_tale(dg_vehicle_No_FC_SOC)
# print('dg_vehicle_Num_CS_SOC')
# get_SOC_tale(dg_vehicle_Num_CS_SOC)
#
# print('dg_vehicle_sub_150_SOC')
# get_SOC_tale(dg_vehicle_sub_150_SOC)
# print('dg_vehicle_sub_250_SOC')
# get_SOC_tale(dg_vehicle_sub_250_SOC)
# print('dg_vehicle_sub_300_SOC')
# get_SOC_tale(dg_vehicle_sub_300_SOC)
#
# print('dg_vehicle_sub_75_SOC')
# get_SOC_tale(dg_vehicle_sub_75_SOC)
# print('dg_vehicle_sub_100_SOC')
# get_SOC_tale(dg_vehicle_sub_100_SOC)
#
#
# print('dg_vehicle_sub_flat_tariff_SOC')
# get_SOC_tale(dg_vehicle_sub_flat_tariff_SOC)
# print('dg_vehicle_sub_high_price_SOC')
# get_SOC_tale(dg_vehicle_sub_high_price_SOC)
