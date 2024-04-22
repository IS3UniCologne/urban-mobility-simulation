import numpy as np
import pandas as pd
from geneticalgorithm import geneticalgorithm as ga

from main import run_single_simulation

# new_population = numpy.random.random_integers(low=30, high=300, size=(20,3))
experience = pd.DataFrame(columns=[0, 1, 2, 3])


def f(i):
    print(i)
    i = [int(numeric_string) for numeric_string in i]
    new_experience = pd.DataFrame([i, i]).drop_duplicates()
    new_experience[3] = "None"
    global experience
    experience = experience.append(new_experience)
    # print(experience)
    objective = -float(
        (
            run_single_simulation(
                end_time=1400, allocation=i, seed=42, substitution=0.1
            )[-1]
        )
    )
    print(objective)
    # experience.loc[
    #     (experience[0] == i[0]) & (experience[1] == i[1]) & (experience[2] == i[2]), 3] = objective
    # # print(experience)
    # experience.to_csv('experience.csv')
    return objective


varbound = np.array([0, 50] * 213).reshape(213, 2)
algorithm_param = {
    "max_num_iteration": 20,
    "population_size": 40,
    "mutation_probability": 0.5,
    "elit_ratio": 0.01,
    "crossover_probability": 0.5,
    "parents_portion": 0.5,
    "crossover_type": "uniform",
    "max_iteration_without_improv": None,
}

model = ga(
    function=f,
    dimension=213,
    variable_type="int",
    function_timeout=150000000,
    variable_boundaries=varbound,
    algorithm_parameters=algorithm_param,
)

model.run()
