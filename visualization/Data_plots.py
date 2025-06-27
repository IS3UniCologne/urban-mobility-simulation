import matplotlib.pyplot as plt

import simpy

from simulation.world.world import World

class DataPlots:

    def __init__(
        self,
        env: simpy.Environment,
        world: World,
        timestamp: list,
        y1: list,
        y2: list,
        y3: list,
        y4: list,
        y5: list,
        y6: list,
    ) -> None:
        self._env = env
        self._world: World = world
        self._timestamp = timestamp
        self._y1 = y1
        self._y2 = y2
        self._y3 = y3
        self._y4 = y4
        self._y5 = y5
        self._y6 = y6

    # callback function
    def get_n_users(self, ridehailing_operator_0, ridehailing_operator_1, charging_infrastructure, world, env) -> list:
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
        self._timestamp.append(env.now)
        self._y1.append(len(world.user_processes))
        self._y2.append(fulfilled_trips_fleet_0)
        self._y3.append(fulfilled_trips_fleet_1)
        self._y4.append(total_trips_fleet_0)
        self._y5.append(total_trips_fleet_1)
        self._y6.append(global_avg_station_utilization)

        return self._timestamp, self._y1, self._y2, self._y3, self._y4, self._y5, self._y6


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
