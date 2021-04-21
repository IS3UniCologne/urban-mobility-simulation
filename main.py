import simulation.world.world as world

# world.run()

import simulation.agent.user as user
from simulation.environment.geodesic_position import GeodesicPosition
from simulation.operator.shared_vehicle_search_engine import SharedVehicleSearchEngine
from simulation.tasks.transport_task import TransportTask
from simulation.vehicle.shared_vehicle import SharedVehicle

pos = GeodesicPosition(13.4, 53.3)

task = TransportTask(pos, pos)

search_engine = SharedVehicleSearchEngine()

x = user.User(pos, "Test", task, search_engine)

vehicle = SharedVehicle(pos)
print(x.position)
vehicle.mount(x)
print(vehicle)
vehicle.dismount(x)
print(vehicle)
vehicle.dismount(x)


# import simpy
# import random
# import statistics
#
# wait_times = []
#
#
# class Theater(object):
#     def __init__(self, env, num_cashiers, num_ushers, num_servers):
#         self.env = env
#         self.cashier = simpy.Resource(env, num_cashiers)
#         self.usher = simpy.Resource(env, num_ushers)
#         self.server = simpy.Resource(env, num_servers)
#
#
#     def purchase_ticket(self, moviegoer):
#         yield self.env.timeout(random.randint(60, 180))
#
#     def check_ticket(self, moviegoer):
#         yield self.env.timeout(random.randint(1, 5))
#
#     def sell_food(self, moviegoer):
#         yield self.env.timeout(random.randint(60, 300))
#
# def go_to_movies(env, moviegoer, theater):
#     # Moviegoer arrives at the theater
#     arrival_time = env.now
#
#     with theater.cashier.request() as request:
#         yield request
#         yield env.process(theater.purchase_ticket(moviegoer))
#
#     with theater.usher.request() as request:
#         yield request
#         yield env.process(theater.check_ticket(moviegoer))
#
#     if random.choice([True, False]):
#             with theater.server.request() as request:
#                 yield request
#                 yield env.process(theater.sell_food(moviegoer))
#
#     # Moviegoer heads into the theater
#     wait_times.append(env.now - arrival_time)
#
# def run_theater(env, num_cashiers, num_servers, num_ushers):
#     theater = Theater(env, num_cashiers, num_servers, num_ushers)
#
#     for moviegoer in range(3):
#         env.process(go_to_movies(env, moviegoer, theater))
#
#     while True:
#         yield env.timeout(12)  # Wait a bit before generating a new person
#
#         moviegoer += 1
#         env.process(go_to_movies(env, moviegoer, theater))
#
# def get_average_wait_time(wait_times):
#     return statistics.mean(wait_times)
#
# def main():
#   # Setup
#   random.seed(42)
#   num_cashiers, num_servers, num_ushers = [1, 1, 1]
#
#   # Run the simulation
#   env = simpy.Environment()
#   env.process(run_theater(env, num_cashiers, num_servers, num_ushers))
#   env.run(until=90*60)
#
#   # View the results
#   average_wait = get_average_wait_time(wait_times)
#   print(
#       "Running simulation...",
#       f"\nThe average wait time is {average_wait/60} minutes.",
#   )
#
#
# if __name__ == '__main__':
#     main()