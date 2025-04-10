import mlrose_hiive as mlrose

from simulation.helper.random.random_manager import RandomManager


def solve_tsp(self, hexagons, distance_matrix):
    """
    Solve the Traveling Salesman Problem for a given set of hexagons using genetic algorithm.
    We switched from mlrose's 2-opt to genetic algorithm for better performance.
    This is just kept for reference.
    The 2-opt algorithm is implemented in the simulation.helper.solvers.tsp_solver_2opt module.

    :param hexagons: Dictionary mapping hexagon IDs to indices
    :param distance_matrix: Distance matrix between hexagons
    :return: Optimized route, best fitness, and distance list
    """
    # Build distance list for mlrose
    dist_list = []
    for i, value_i in hexagons.items():
        for j, value_j in hexagons.items():
            if i != j:
                dist_list.append((value_i, value_j, distance_matrix.loc[j][i]))

    # Initialize fitness function object using dist_list
    fitness_dists = mlrose.TravellingSales(distances=dist_list)

    # Define optimization problem object
    problem_fit = mlrose.TSPOpt(
        length=len(hexagons), fitness_fn=fitness_dists, maximize=False
    )

    # Solve problem using the genetic algorithm (keep random state constant)
    seed = RandomManager().integers(0, 1000000, component="SHAREDMOBILITYOPERATIONS")
    best_state, best_fitness, _ = mlrose.genetic_alg(
        problem_fit, random_state=seed, curve=False
    )

    # Convert Numpy Array to List
    best_state = best_state.tolist()

    return best_state, best_fitness, dist_list
