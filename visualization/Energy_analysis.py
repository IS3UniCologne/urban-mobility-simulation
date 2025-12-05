import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def clean(x):  # noqa: ANN001, ANN201
    if type(x) is not float:
        x = x.replace("[", "").replace("]", "")
    return x


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


def data_preparation(df_raw):  # noqa: ANN001, ANN201
    df_raw["phase"] += 1
    df_raw.fillna(value=0)
    df_raw["total_profit_ride_hailing"] = (
        df_raw["total_cost_per_day_ride_hailing"] + df_raw["total_profit_ride_hailing"]
    )
    df_raw["waiting_time"] = (
        df_raw["AutonomousCar_True_waiting_time"]
        + df_raw["RideHailingCar_True_waiting_time"]
        + df_raw["RideHailingCar_False_waiting_time"]
    )
    df_raw["pick_up_time"] = (
        df_raw["AutonomousCar_True_pick_up_time"]
        + df_raw["RideHailingCar_True_pick_up_time"]
        + df_raw["RideHailingCar_False_pick_up_time"]
    )
    df_raw["total_waiting_time"] = (
        df_raw["waiting_time"] + df_raw["pick_up_time"]
    ) / df_raw["total_fulfilled_trips_ride_hailing"]
    df_raw["service_quality"] = (df_raw["total_fulfilled_trips_ride_hailing"]) / 7600
    df_raw["distance_HV"] = (
        df_raw["RideHailingCar_True_distance"] + df_raw["RideHailingCar_False_distance"]
    )
    df_raw["distance_AV"] = df_raw["AutonomousCar_True_distance"]
    df_raw["total_distance"] = df_raw["distance_HV"] + df_raw["distance_AV"]
    df_raw["Energy_Consumed_HV"] = (
        df_raw["RideHailingCar_True_distance"] * 75 / 1000
        + df_raw["RideHailingCar_False_distance"] * 241 / 1000
    )
    df_raw["Energy_Consumed_AV"] = df_raw["AutonomousCar_True_distance"] * 75 / 1000

    df_raw["total_Energy_Consumed"] = (
        (df_raw["Energy_Consumed_HV"] + df_raw["Energy_Consumed_AV"])
        / df_raw["service_quality"]
        / 7600
    )
    # for i in range(4):
    #     df_raw.loc[(df_raw['phase']==i), 'Energy_Consumed_HV'] = df_raw.loc[(df_raw['phase']==i), 'Energy_Consumed_HV'] / 300 ()
    return df_raw


def plot_CS_Benchmark(dg):  # noqa: ANN001, ANN201
    set_style()
    _, ax = plt.subplots(nrows=1, ncols=2, figsize=(12, 4), constrained_layout=True)
    HUE = "scenario"
    N_COLORS = 5
    DODGE = True
    X = "phase"
    X_LABLE = "Technology Phases"
    Y = ["total_Energy_Consumed", "total_Energy_Consumed"]
    Y_LABLE = ["CO2(gr)", "CO2(gr)", "CO2(gr)", "Time(minute)"]
    Title = [
        "Fleet Carbon Emission: Hard Criteria",
        "Fleet Carbon Emission: Soft Criteria",
        "Total Carbon Emission",
        "Waiting Time",
    ]
    # Y_LIMIT_UP = [45000, 24000, 8000]
    # Y_LIMIT_LO = [30000, 5000, 6500]

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
        sns.barplot(
            data=dg[i],
            x=X,
            y=Y[i],
            hue=HUE,
            palette=sns.color_palette("mako", n_colors=N_COLORS),
            ax=ax[i],
            dodge=DODGE,
        )
        ax[i].set_ylim(0, 900)
        ax[i].set_xlabel(X_LABLE, fontsize=12)
        ax[i].set_ylabel(Y_LABLE[i], fontsize=12)
        ax[i].set_title(Title[i], fontsize=12)
        ax[i].tick_params(axis="both", labelsize=8)

    plt.savefig(
        "/home/rahadi/Projects/urban-mobility-simulation/data/output/energy.pdf"
    )
    plt.show()


df_raw_results = pd.DataFrame()
dg = {}
for i in range(5):
    base_path = f"/home/rahadi/Projects/urban-mobility-simulation/data/output/scenario_{i + 1}_500_all_simulation_results.csv"
    new_df = pd.read_csv(base_path)
    new_df["scenario"] = f"{i + 1}"
    df_raw_results = pd.concat([df_raw_results, new_df], axis=0)
    # dg[i] = data_preparation(df_raw_results)
dg[0] = data_preparation(df_raw_results)
df_raw_results = pd.DataFrame()
for i in range(5):
    base_path = f"/home/rahadi/Projects/urban-mobility-simulation/data/output/scenario_{i + 6}_500_all_simulation_results.csv"
    new_df = pd.read_csv(base_path)
    new_df["scenario"] = f"{i + 6}"
    df_raw_results = pd.concat([df_raw_results, new_df], axis=0)
    # dg[i] = data_preparation(df_raw_results)
dg[1] = data_preparation(df_raw_results)

plot_CS_Benchmark(dg)
