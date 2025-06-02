import ga
import matplotlib.pyplot
import numpy
import pandas as pd

# TODO: Adding constraints (number of connectors and number of chargers)
from main import run_single_simulation


def fitness_function(generation, experience):  # noqa: ANN001, ANN201
    objectives = []
    for i in generation:
        value = experience.loc[
            (experience[0] == i[0]) & (experience[1] == i[1]) & (experience[2] == i[2]),
            4,
        ].values[0]
        if value == "None":
            objective = run_single_simulation(
                end_time=1400,
                n_cars=i[0],
                n_scooter=i[1],
                n_kick_scooter=i[2],
                seed=42,
                substitution=0.1,
            )[-1]
            experience.loc[
                (experience[0] == i[0])
                & (experience[1] == i[1])
                & (experience[2] == i[2]),
                4,
            ] = objective
        else:
            objective = value
        objectives.append(objective)
        print(objectives)  # noqa: T201
    return objectives, experience


num_weights = 3

sol_per_pop = 20
num_parents_mating = 10

# Defining the population size.
pop_size = (
    sol_per_pop,
    num_weights,
)  # The population will have sol_per_pop chromosome where each chromosome has num_weights genes.
# Creating the initial population.
first_generation = "from_experience"
approximation = "hundreds"
if first_generation == "random":
    new_population = numpy.random.random_integers(low=50, high=2000, size=pop_size)
    for i in range(pop_size[0]):
        for j in range(pop_size[1]):
            if j == 0:
                new_population[i, j] = numpy.random.random_integers(
                    low=800, high=1500, size=1
                )
            elif j == 1:
                new_population[i, j] = numpy.random.random_integers(
                    low=500, high=1000, size=1
                )
            else:
                new_population[i, j] = numpy.random.random_integers(
                    low=200, high=800, size=1
                )
    experience = pd.DataFrame(new_population.copy())
    experience[4] = "None"
if first_generation == "from_experience":
    experience = pd.read_csv("experience.csv").drop("Unnamed: 0", axis=1)
    experience.columns = [0, 1, 2, 4]
    experience = experience.loc[experience[4] != "None"]
    experience[4] = experience[4].astype("float")
    new_population = (
        experience.sort_values([4], ascending=False).head(20)[[0, 1, 2]].to_numpy()
    )
    if approximation == "hundreds":
        new_population = numpy.round(new_population / 10) * 10
        new_experience = pd.DataFrame(new_population)
        new_experience[4] = "None"
        experience = experience.append(new_experience)

print(new_population)  # noqa: T201

best_outputs = []
num_generations = 100

for generation in range(num_generations):
    print("Generation : ", generation)  # noqa: T201
    # Measuring the fitness of each chromosome in the population.
    output = fitness_function(new_population, experience)
    fitness = output[0]
    experience = output[1]
    print("Fitness")  # noqa: T201
    print(fitness)  # noqa: T201
    print(experience)  # noqa: T201

    # best_outputs.append(numpy.max(numpy.sum(new_population * equation_inputs, axis=1)))
    # # The best result in the current iteration.
    # print("Best result : ", numpy.max(numpy.sum(new_population * equation_inputs, axis=1)))

    # Selecting the best parents in the population for mating.
    parents = ga.select_mating_pool(new_population, fitness, num_parents_mating)
    print("Parents")  # noqa: T201
    print(parents)  # noqa: T201

    # Generating next generation using crossover.
    offspring_crossover = ga.crossover(
        parents, offspring_size=(pop_size[0] - parents.shape[0], num_weights)
    )
    if approximation == "hundreds":
        offspring_crossover = numpy.round(offspring_crossover / 10) * 10
    print("Crossover")  # noqa: T201
    print(offspring_crossover)  # noqa: T201

    # Adding some variations to the offspring using mutation.
    offspring_mutation = ga.mutation(
        offspring_crossover,
        num_mutations=1,
        mutation_rate=max(0.5, (0.8 - generation * 0.01)),
    )

    print("Mutation")  # noqa: T201
    print(offspring_mutation)  # noqa: T201

    # Creating the new population based on the parents and offspring.
    new_population[0 : parents.shape[0], :] = parents
    new_population[parents.shape[0] :, :] = offspring_mutation
    new_experience = pd.DataFrame(offspring_mutation)
    new_experience[4] = "None"
    experience = experience.append(new_experience)
    experience.to_csv("experience.csv")

# Getting the best solution after iterating finishing all generations.
# At first, the fitness is calculated for each solution in the final generation.
fitness = fitness_function(new_population)
# Then return the index of that solution corresponding to the best fitness.
best_match_idx = numpy.where(fitness == numpy.max(fitness))

print("Best solution : ", new_population[best_match_idx, :])  # noqa: T201
# print("Best solution fitness : ", fitness[best_match_idx])

matplotlib.pyplot.plot(best_outputs)
matplotlib.pyplot.xlabel("Iteration")
matplotlib.pyplot.ylabel("Fitness")
matplotlib.pyplot.show()
