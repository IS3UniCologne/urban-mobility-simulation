import matplotlib.pyplot as plt


# # # # # # # # # # # # # # # # # # # # # #
#                                         #
# Live Visualization                      #
#                                         #
# # # # # # # # # # # # # # # # # # # # # #

timestamp = []
y1, y2, y3, y4, y5, y6, y7 = [], [], [], [], [], [], []


# callback function to get data from world
def get_n_users(ridehailing_operator_0, ridehailing_operator_1, charging_infrastructure, env) -> list:
    # fulfilled trips vs. total trips
    fleet_0_transactions = ridehailing_operator_0.transaction_df
    fleet_1_transactions = ridehailing_operator_1.transaction_df

    try:
        fulfilled_trips_fleet_0 = (
            fleet_0_transactions["state"].apply(lambda x: "Fulfilled" in x).sum()
        )
        fulfilled_trips_fleet_1 = (
            fleet_1_transactions["state"].apply(lambda x: "Fulfilled" in x).sum()
        )
        total_trips_fleet_0 = len(fleet_0_transactions["state"])
        total_trips_fleet_1 = len(fleet_1_transactions["state"])
    except Exception:
        fulfilled_trips_fleet_0 = 0
        fulfilled_trips_fleet_1 = 0
        total_trips_fleet_0 = 0
        total_trips_fleet_1 = 0

    # global avg station utilization
    global_station_utilization = 0
    for charging_station in charging_infrastructure.charging_stations:
        global_station_utilization += charging_station.plugs.count

    global_avg_station_utilization = global_station_utilization / len(
        charging_infrastructure.charging_stations
    )

    # add all data to dictionary
    timestamp.append(env.now)
    y1.append(len(world.user_processes))
    y2.append(fulfilled_trips_fleet_0)
    y3.append(fulfilled_trips_fleet_1)
    y4.append(total_trips_fleet_0)
    y5.append(total_trips_fleet_1)
    y6.append(global_avg_station_utilization)
    return timestamp, y1, y2, y3, y4, y5, y6


def animate(i: int, callback: list) -> None:
    if callback is not None:
        (
            timestamp,
            n_active_users,
            fulfilled_trips_0,
            fulfilled_trips_1,
            total_trips_0,
            total_trips_1,
            avg_station_util,
        ) = callback()

        # clear whole figure
        plt.clf()

        # plot 1
        plt.subplot(4, 1, 1)
        plt.plot(timestamp, fulfilled_trips_0, total_trips_0)
        plt.title("fulfilled vs. total trips (fleet 0)")
        plt.legend(["fulfilled_trips_0", "total_trips_0"], loc="upper right")

        # plot 2
        plt.subplot(4, 1, 2)
        plt.plot(timestamp, fulfilled_trips_1, total_trips_1)
        plt.title("fulfilled vs. total trips (fleet 1)")
        plt.legend(["fulfilled_trips_1", "total_trips_1"], loc="upper right")

        # plot 3
        plt.subplot(4, 1, 3)
        plt.plot(timestamp, n_active_users)
        plt.title("active users")

        # plot 4
        plt.subplot(4, 1, 4)
        plt.plot(timestamp, avg_station_util)
        plt.title("global average charging station utilization")

        plt.tight_layout()
