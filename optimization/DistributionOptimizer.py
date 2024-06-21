import random
import numpy as np
import pandas as pd
from deap import base, creator, tools, algorithms
from deap.algorithms import varAnd

from .CandidateFactory import CandidateFactory
import os
import pickle
import multiprocessing
from deap import algorithms
import shutil

def get_fitness_values(individual):
    return individual.fitness.values

class DistributionOptimizer:

    def __init__(self, max_fleet_size, is_maximization):
        self._max_fleet_size = max_fleet_size
        self._toolbox = base.Toolbox()
        self._is_maximization = is_maximization

    def build(self, evaluate):

        if self._is_maximization:
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
            creator.create("Individual", list, fitness=creator.FitnessMax)
        else:
            creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
            creator.create("Individual", list, fitness=creator.FitnessMin)

        can_factory = CandidateFactory(self._max_fleet_size)

        self._toolbox.register("individual", tools.initIterate, creator.Individual, can_factory.get_ind)
        self._toolbox.register("population", tools.initRepeat, list, self._toolbox.individual)

        self._toolbox.register("mate", self.crossover)
        self._toolbox.register("select", tools.selTournament, tournsize=3)

        self._toolbox.register("mutate", self.mutate)

        self._toolbox.register("evaluate", evaluate)


    # Crossover function to create two children elements based on two parents
    def crossover(self, ind1, ind2):
        size = len(ind1)
        cxpoint1 = random.randint(1, size - 1)
        cxpoint2 = random.randint(1, size - 1)
        if cxpoint1 > cxpoint2:
            cxpoint1, cxpoint2 = cxpoint2, cxpoint1

        # Perform the crossover between the two points
        temp1 = ind1[:cxpoint1] + ind2[cxpoint1:cxpoint2] + ind1[cxpoint2:]
        temp2 = ind2[:cxpoint1] + ind1[cxpoint1:cxpoint2] + ind2[cxpoint2:]

        # Apply the adjustment to ensure the sums are max fleet size
        self.adjust_to_total(temp1, self._max_fleet_size)
        self.adjust_to_total(temp2, self._max_fleet_size)

        print(f'Crossover of: {ind1} {ind2}')

        # Replace original individuals
        ind1[:], ind2[:] = temp1, temp2

        print(f'To: {ind1} {ind2}')
        return ind1, ind2

    # Adjust function to ensure no negative numbers and total is equal to the max fleet size
    def adjust_to_total(self, individual, target_sum):
        size = len(individual)
        current_sum = sum(individual)
        diff = target_sum - current_sum
        adjustments = [0] * size
        while diff != 0:
            for i in range(size):
                if diff > 0 and individual[i] + adjustments[i] < target_sum:
                    adjustments[i] += 1
                    diff -= 1
                elif diff < 0 and individual[i] + adjustments[i] > 0:
                    adjustments[i] -= 1
                    diff += 1
                if diff == 0:
                    break

        for i in range(size):
            individual[i] += adjustments[i]

        return individual

    # Function to create a new mutation by changing one element of the list randomly up or down
    def mutate(self, individual):
        index = random.randrange(4)
        max_increase = min(100, self._max_fleet_size - individual[index])

        # So that the max decrease is max 0
        max_decrease = min(100, individual[index])

        change = random.randint(-max_decrease, max_increase)
        individual[index] += change

        # After the change we need to adjust the other elements, so that the sum of individual is not greater than MAX_FLEET_SIZE
        while not sum(individual) == self._max_fleet_size:
            other_index = random.choice([i for i in range(4) if i != index])

            if individual[other_index] - change >= 0 & individual[other_index] - change <= self._max_fleet_size:
                individual[other_index] -= change

        print(f'Mutate: {individual}')
        return individual,

    def save_checkpoint(self, population, halloffame, stats, gen, filename):
        cp = dict(population=population, halloffame=halloffame, stats=stats, generation=gen)
        with open(filename, "wb") as cp_file:
            pickle.dump(cp, cp_file)

    def load_checkpoint(self, filename):
        with open(filename, "rb") as cp_file:
            cp = pickle.load(cp_file)
        return cp['population'], cp['halloffame'], cp['stats'], cp['generation']

    def optimize(self, population_size, num_generations, rn, checkpoint=None):

        os.makedirs("data/output/simulation_logs/progress", exist_ok=True)
        os.makedirs("data/output/simulation_logs/final", exist_ok=True)
        verbose = True
        cxpb = 0.5
        mutpb = 0.5

        pop = self._toolbox.population(n=population_size)
        hof = tools.HallOfFame(1)
        stats = tools.Statistics(get_fitness_values)
        stats.register("avg", np.mean)
        stats.register("min", np.min)
        stats.register("max", np.max)

        history = tools.Statistics(lambda ind: ind)
        history.register('hof', lambda pop: hof[0])
        mstats = tools.MultiStatistics(fitness=stats, history=history)

        logbook = tools.Logbook()
        logbook.header = ['gen', 'nevals'] + (stats.fields if stats else [])

        # Evaluate the individuals with an invalid fitness
        invalid_ind = [ind for ind in pop if not ind.fitness.valid]
        fitnesses = self._toolbox.map(self._toolbox.evaluate, invalid_ind)
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit

        if hof is not None:
            hof.update(pop)

        record = stats.compile(pop) if stats else {}
        logbook.record(gen=0, nevals=len(invalid_ind), **record)
        if verbose:
            print(logbook.stream)

        # Begin the generational process
        for gen in range(1, num_generations + 1):
            # Select the next generation individuals
            offspring = self._toolbox.select(pop, len(pop))

            # Vary the pool of individuals
            offspring = varAnd(offspring, self._toolbox, cxpb, mutpb)

            # Evaluate the individuals with an invalid fitness
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = self._toolbox.map(self._toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit

            # Update the hall of fame with the generated individuals
            if hof is not None:
                hof.update(offspring)

            # Replace the current population by the offspring
            pop[:] = offspring

            # Append the current generation statistics to the logbook
            record = stats.compile(pop) if stats else {}
            logbook.record(gen=gen, nevals=len(invalid_ind), **record)
            if verbose:
                print(logbook.stream)

            rn.increase_gen()


        pop, mlogbook = algorithms.eaSimple(pop, self._toolbox, cxpb=0.5, mutpb=0.5, ngen=num_generations,
                                            stats=mstats, halloffame=hof, verbose=True)

        # for gen in range(start_gen, num_generations):
        #
        #     if gen % 2 == 0:
        #         self.save_checkpoint(pop, hof, stats, gen,
        #                              f"data/output/simulation_logs/progress/checkpoint_gen_{gen}.pkl")

        print("End of Optimization")
        print("Beste Lösung:", hof[0], "Relative Revenue:", hof[0].fitness.values[0])
        print(mlogbook.chapters["fitness"].select("gen"))
        hof_list = mlogbook.chapters["history"].select("hof")

        if self._is_maximization:
            val_list = mlogbook.chapters["fitness"].select("max")
        else:
            val_list = mlogbook.chapters["fitness"].select("min")

        print(hof)

        unique_dict = {}
        seen_elements = set()

        for index, element in enumerate(hof_list):
            if str(element) not in seen_elements:
                unique_dict[index] = {"dist": element, "val": val_list[index]}
                seen_elements.add(str(element))

        for key, value in unique_dict.items():
            tmp_list = pd.read_excel(
                f'data/output/simulation_logs/progress/tran_c_{value["dist"][0]}_s_{value["dist"][1]}_ks_{value["dist"][2]}_b_{value["dist"][3]}.xlsx')
            tmp_list.to_excel(
                f'data/output/simulation_logs/final/gen_{key}_res_{value["val"]}_tran_c_{value["dist"][0]}_s_{value["dist"][1]}_ks_{value["dist"][2]}_b_{value["dist"][3]}.xlsx')

        shutil.rmtree(f'data/output/simulation_logs/progress')