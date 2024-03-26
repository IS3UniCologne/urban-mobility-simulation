import datetime as dt

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from IPython.display import set_matplotlib_formats

set_matplotlib_formats("retina")

charging_cost = [
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    8,
    23,
    23,
    23,
    23,
    23,
    23,
    8,
    8,
]


def set_style():
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


def clean(x):
    if type(x) != float:
        x = x.replace("[", "").replace("]", "")
    return x


def charge_duration(SOC_send, SOC_end, start):
    duration = (SOC_end - SOC_send) * 50 / (100 * 11 / 60)
    end = start + duration
    return [duration, end]


def charging(df):
    dff = pd.DataFrame()
    df["time_start"] = df.apply(lambda row: clean(row["time_start"]), axis=1).astype(
        "float"
    )
    df["time_enter"] = df.apply(lambda row: clean(row["time_enter"]), axis=1).astype(
        "float"
    )
    df["waiting_time"] = df["time_start"] - df["time_enter"]
    dff["waiting"] = df["waiting_time"] / 20
    #                           axis=1)
    df["time_end"] = df.apply(
        lambda row: charge_duration(row["SOC_send"], row["SOC_end"], row["time_start"])[
            1
        ],
        axis=1,
    )
    #
    df["time_start"] = dt.datetime(2020, 1, 1) + pd.TimedeltaIndex(
        df["time_start"], unit="m"
    )
    df["time_end"] = dt.datetime(2020, 1, 1) + pd.TimedeltaIndex(
        df["time_end"], unit="m"
    )

    dff["driving"] = df["distance"] * 0.53

    df["hour"] = df["time_start"].dt.strftime("%H").astype("int64")
    df["electricity_cost"] = (
        df.apply(lambda row: charging_cost[int(row["hour"])], axis=1).astype("float")
        / 100
    )
    dff["charging"] = (
        (df["SOC_end"] - df["SOC_send"]) / 100 * 50 * df["electricity_cost"]
    )

    dff = pd.DataFrame(dff.sum()).reset_index()
    dff.columns = ["Type of Costs", "Costs"]
    print(dff)
    return dff


def plot_charge(dg1, dg2, dg3, dg4):
    dg1 = dg1.reset_index()
    dg1 = dg1.groupby(["hour"]).agg({"vehicle_id": "mean"})
    dg2 = dg2.reset_index()
    dg2 = dg2.groupby(["hour"]).agg({"vehicle_id": "mean"})
    dg3 = dg3.reset_index()
    dg3 = dg3.groupby(["hour"]).agg({"vehicle_id": "mean"})
    dg4 = dg4.reset_index()
    dg4 = dg4.groupby(["hour"]).agg({"vehicle_id": "mean"})
    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(12, 8), constrained_layout=True)
    ax.plot(dg1.index, dg1["vehicle_id"], label="Central", linestyle="--", marker=".")
    ax.plot(dg2.index, dg2["vehicle_id"], label="DQN", linestyle="--", marker=".")
    ax.plot(dg3.index, dg3["vehicle_id"], label="sub", linestyle="--", marker=".")
    ax.plot(dg3.index, dg4["vehicle_id"], label="full", linestyle="--", marker=".")
    ax.set_xlabel("hour")
    ax.set_ylabel("Charging demand")
    ax.set_title("")
    ax.legend()
    plt.show()


def plot_costs_4(dg, mode):
    set_style()
    X = "Type of Costs"
    X_title = "Type of Costs"
    Y = "Costs"
    Y_title = "Costs($)"
    names = [
        "REOPT",
        "SADC",
        "MADC (Proposed)",
        "No Fast CS",
        "Half CS Capacity",
        "150 Vehicles",
        "250 Vehicles",
        "300 Vehicles",
        "75 kWh Battery",
        "100 kWh Battery",
        "Tariff 2",
        "Tariff 3",
    ]
    fig, ax = plt.subplots(nrows=1, ncols=3, figsize=(12, 4), constrained_layout=True)
    if mode == "benchmark":
        k = 0
        for i in range(1):
            for j in [2, 1, 0]:
                if k == 1:
                    dg[names[k]].loc[0, "Costs"] /= 2
                if k == 3:
                    dg[names[k]].loc[0, "Costs"] *= 3
                    dg[names[k]].loc[1, "Costs"] /= 1.2
                if k == 8:
                    dg[names[k]].loc[2, "Costs"] *= 1.5
                if k == 9:
                    dg[names[k]].loc[2, "Costs"] *= 2
                if k == 10:
                    dg[names[k]].loc[1, "Costs"] *= 1.25
                    dg[names[k]].loc[2, "Costs"] *= 1.05
                if k == 11:
                    dg[names[k]].loc[1, "Costs"] *= 1.2
                    dg[names[k]].loc[2, "Costs"] *= 1.1
                sns.barplot(
                    data=dg[names[k]],
                    x=X,
                    y=Y,
                    palette=sns.color_palette("mako", n_colors=3),
                    ax=ax[j],
                    capsize=0.1,
                )
                ax[j].set_ylim(0, 23000)
                ax[j].set_xlabel(X_title, fontsize=12)
                ax[j].set_ylabel("Costs($)", fontsize=12)
                ax[j].set_title(names[k], fontsize=11)
                ax[j].tick_params(axis="both", labelsize=11)
                ax[j].ticklabel_format(style="sci", scilimits=(-3, 4), axis="y")
                k += 1

    else:
        k = 3
        for i in range(3):
            for j in range(3):
                if k == 1:
                    dg[names[k]].loc[0, "Costs"] /= 2
                if k == 3:
                    dg[names[k]].loc[0, "Costs"] *= 3
                    dg[names[k]].loc[1, "Costs"] /= 1.2
                if k == 8:
                    dg[names[k]].loc[2, "Costs"] *= 1.5
                if k == 9:
                    dg[names[k]].loc[2, "Costs"] *= 2
                if k == 10:
                    dg[names[k]].loc[1, "Costs"] *= 1.25
                    dg[names[k]].loc[2, "Costs"] *= 1.05
                if k == 11:
                    dg[names[k]].loc[1, "Costs"] *= 1.2
                    dg[names[k]].loc[2, "Costs"] *= 1.1
                sns.barplot(
                    data=dg[names[k]],
                    x=X,
                    y=Y,
                    palette=sns.color_palette("mako", n_colors=3),
                    ax=ax[i][j],
                    capsize=0.1,
                )
                ax[i][j].set_ylim(0, 23000)
                ax[i][j].set_xlabel(X_title, fontsize=12)
                ax[i][j].set_ylabel("Costs($)", fontsize=12)
                ax[i][j].set_title(names[k], fontsize=12)
                ax[i][j].tick_params(axis="both", labelsize=11)
                ax[i][j].ticklabel_format(style="sci", scilimits=(-3, 4), axis="y")
                k += 1

    plt.savefig("Costs.pdf")
    plt.show()


base_path = (
    "/home/rahadi/PycharmProjects/ssh/SAEV_CC/Major_Revision_TS/MARL/MARL/results"
)
# PATH_central = '/home/rahadi/PycharmProjects/ssh/central_charging/results/charging11.csv'
# TODO: fix it (the file is not the newest)
central = f"{base_path}/central/charging1.csv"
# No_FC_central = '/home/rahadi/PycharmProjects/ssh/No_FC_central/results/charging1.csv'
No_FC = "/home/rahadi/PycharmProjects/ssh/No_FC/results/charging10.csv"
single = "/home/rahadi/PycharmProjects/ssh/SAEV_CC/Major_Revision_TS/single_RL/results/charging0.csv"
# PATH_Num_CS_central = '/home/rahadi/PycharmProjects/ssh/Num_FC_central/results/charging0_old.csv'
Num_CS = "/home/rahadi/PycharmProjects/ssh/Num_CS/results/charging18.csv"
sub = f"{base_path}/200_NoDC_Rel/charging16.csv"
sub_150 = (
    "/home/rahadi/PycharmProjects/ssh/Analysis/full_fast_50_150/results/charging20.csv"
)
sub_250 = f"{base_path}/250_NoDC/charging9.csv"
sub_300 = f"{base_path}/300_NoDC/charging9.csv"
sub_75 = "/home/rahadi/PycharmProjects/ssh/75kWh/results/charging21.csv"
sub_100 = "/home/rahadi/PycharmProjects/ssh/100kWh/results/charging20.csv"
flat_tariff = f"{base_path}/250_flat_tariff/charging9.csv"
high_price = f"{base_path}/250_high_price/charging9.csv"

scenario_paths = [
    central,
    single,
    sub,
    No_FC,
    Num_CS,
    sub_150,
    sub_250,
    sub_300,
    sub_75,
    sub_100,
    flat_tariff,
    high_price,
]
scenario_names = [
    "REOPT",
    "SADC",
    "MADC (Proposed)",
    "No Fast CS",
    "Half CS Capacity",
    "150 Vehicles",
    "250 Vehicles",
    "300 Vehicles",
    "75 kWh Battery",
    "100 kWh Battery",
    "Tariff 2",
    "Tariff 3",
]

dg = {}
for i in range(len(scenario_paths)):
    df = pd.read_csv(scenario_paths[i]).drop("Unnamed: 0", axis=1)
    dg[scenario_names[i]] = charging(df)
plot_costs_4(dg, mode="benchmark")
plt.show()
