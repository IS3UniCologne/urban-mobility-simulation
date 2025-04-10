import pandas as pd


def solve_tsp(
    hexagons: dict, distance_matrix: pd.DataFrame
) -> tuple[list[int], float, list[tuple[int, int, float]]]:
    """
    Solve the Traveling Salesman Problem for a given set of hexagons using the 2-opt algorithm.

    :param hexagons: Dictionary mapping hexagon IDs to indices
    :param distance_matrix: Distance matrix between hexagons
    :return: Optimized route, best fitness, and distance list
    """
    # Build distance list for our solver
    dist_list = []
    for i, value_i in hexagons.items():
        for j, value_j in hexagons.items():
            if i != j:
                dist_list.append((value_i, value_j, distance_matrix.loc[j][i]))

    # Create a distance lookup dictionary for faster access
    dist_lookup = {}
    for origin, dest, dist in dist_list:
        dist_lookup[(origin, dest)] = dist

    n = len(hexagons)

    # Initialize with a simple sequential tour
    tour = list(range(n))

    # Calculate initial tour length
    tour_length = calculate_tour_length(tour, dist_lookup)
    # Apply 2-opt improvement
    improved = True
    # Limit iterations, should realistically never reach this in our use case
    max_iterations = 100
    iterations = 0

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1

        for i in range(n - 2):
            for j in range(i + 2, n):
                # Consider swapping edges (i,i+1) and (j,j+1)
                # Where j+1 wraps around to 0 if j is the last index
                current_cost = dist_lookup.get(
                    (tour[i], tour[i + 1]), 0
                ) + dist_lookup.get((tour[j], tour[(j + 1) % n]), 0)
                new_cost = dist_lookup.get((tour[i], tour[j]), 0) + dist_lookup.get(
                    (tour[i + 1], tour[(j + 1) % n]), 0
                )

                if new_cost < current_cost:
                    # Reverse the segment between i+1 and j
                    tour[i + 1 : j + 1] = reversed(tour[i + 1 : j + 1])
                    tour_length = tour_length - current_cost + new_cost
                    improved = True
                    break

            if improved:
                break

    # Calculate final tour  (length)
    best_fitness = calculate_tour_length(tour, dist_lookup)

    return tour, best_fitness, dist_list


def calculate_tour_length(
    tour: list[int], dist_lookup: dict[tuple[int, int], float]
) -> float:
    """
    Calculate the total length of a tour.

    :param tour: A list of node indices representing the tour
    :param dist_lookup: Dictionary mapping node pairs to distances
    :return: Total tour length
    """
    length = 0
    n = len(tour)

    for i in range(n):
        j = (i + 1) % n  # Next node (wraps around)
        length += dist_lookup.get((tour[i], tour[j]), 0)

    return length
