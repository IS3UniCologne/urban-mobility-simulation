import random
import numpy as np
import pandas as pd
from deap import base, creator, tools, algorithms
from deap.algorithms import varAnd

from .CandidateFactory import CandidateFactory
import os
import pickle
from deap import algorithms
import shutil
import logging

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

        logging.info(f'Crossover of: {ind1} {ind2}')

        # Replace original individuals
        ind1[:], ind2[:] = temp1, temp2

        logging.info(f'To: {ind1} {ind2}')
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
        logging.info(f'Call Mutate: {type(individual)}')
        logging.info(f'Call Mutate: {individual}')

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

        logging.info(f'Mutate: {individual}')
        return individual,

    def save_checkpoint(self, population, halloffame, stats, gen, filename):
        cp = dict(population=population, halloffame=halloffame, stats=stats, generation=gen)
        with open(filename, "wb") as cp_file:
            pickle.dump(cp, cp_file)

    def load_checkpoint(self, filename):
        with open(filename, "rb") as cp_file:
            cp = pickle.load(cp_file)
        return cp['population'], cp['halloffame'], cp['stats'], cp['generation']


    # TODO Add checkpoint
    # TODO add lo
    def optimize(self, population_size, num_generations, current_sim_id, checkpoint=None):

        os.makedirs(f'data/output/simulation_logs/{current_sim_id}/final', exist_ok=True)
        verbose = True
        cxpb = 0.5
        mutpb = 0.5

        if checkpoint:
            pop, hof, stats, start_gen = self.load_checkpoint(checkpoint)
            print('check-----')
            print(pop, hof, stats, start_gen)
            history = tools.Statistics(lambda ind: ind)
            history.register('hof', lambda pop: hof[0])
            mstats = tools.MultiStatistics(fitness=stats, history=history)

            logbook = tools.Logbook()
            logbook.header = ['gen', 'nevals'] + (mstats.fields if mstats else [])

        else:
            pop = self._toolbox.population(n=population_size)
            hof = tools.HallOfFame(1)
            stats = tools.Statistics(get_fitness_values)
            stats.register("avg", np.mean)
            stats.register("min", np.min)
            stats.register("max", np.max)
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_0', exist_ok=True)
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_0/transactions', exist_ok=True)
            start_gen = 0

            history = tools.Statistics(lambda ind: ind)
            history.register('hof', lambda pop: hof[0])
            mstats = tools.MultiStatistics(fitness=stats, history=history)

            logbook = tools.Logbook()
            logbook.header = ['gen', 'nevals'] + (mstats.fields if mstats else [])

            # Evaluate the individuals with an invalid fitness
            invalid_ind = [(ind, start_gen) for ind in pop if not ind.fitness.valid]
            fitnesses = self._toolbox.map(self._toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind[0].fitness.values = fit

            if hof is not None:
                hof.update(pop)

            record = mstats.compile(pop) if mstats else {}
            logbook.record(gen=start_gen, nevals=len(invalid_ind), **record)
            if verbose:
                logging.info(logbook.stream)

        # Begin the generational process
        for gen in range(start_gen+1, num_generations + 1):
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_{gen}', exist_ok=True)
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_{gen}/transactions', exist_ok=True)
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_{gen}/checkpoint', exist_ok=True)

            # Select the next generation individuals
            offspring = self._toolbox.select(pop, len(pop))

            # Vary the pool of individuals
            offspring = varAnd(offspring, self._toolbox, cxpb, mutpb)

            # Evaluate the individuals with an invalid fitness, create a tuple of ind and gen
            # TODO: Idea for making it parallelizeable, [(ind, gen) for ind in offspring if not ind.fitness.valid]
            invalid_ind = [(ind, gen) for ind in offspring if not ind.fitness.valid]
            fitnesses = self._toolbox.map(self._toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind[0].fitness.values = fit

            # Update the hall of fame with the generated individuals
            if hof is not None:
                hof.update(offspring)

            # Replace the current population by the offspring
            pop[:] = offspring

            # Append the current generation statistics to the logbook
            record = mstats.compile(pop) if mstats else {}
            logbook.record(gen=gen, nevals=len(invalid_ind), **record)

            logging.info("logbook-------")
            logging.info(logbook)

            logging.info("hof-------")
            logging.info(hof)

            if verbose:
                logging.info(logbook.stream)

            # Save checkpoint of current generation
            self.save_checkpoint(pop, hof, stats, gen, f"data/output/simulation_logs/{current_sim_id}/gen_{gen}/checkpoint/gen_{gen}.pkl")

        logging.info("End of Optimization")
        logging.info(f'Best Solution: {hof[0]} Relative Revenue: {hof[0].fitness.values[0]}')
        logging.info(logbook.chapters["fitness"].select("gen"))

        df_log = pd.DataFrame(logbook.chapters["history"])
        df_log.to_excel(f'data/output/simulation_logs/{current_sim_id}/ea_alg_metrics.xlsx')

