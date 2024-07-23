import random
import numpy as np
import pandas as pd
from deap import base, creator, tools, algorithms
from deap.algorithms import varAnd
import re

from .CandidateFactory import CandidateFactory
import os
import pickle
from deap import algorithms
import shutil
import logging
import multiprocessing
import copy

def get_fitness_values(individual):
    return individual.fitness.values

class DistributionOptimizer:

    def __init__(self, max_fleet_size, is_maximization, with_multi_processing=False):
        self._max_fleet_size = max_fleet_size
        self._toolbox = base.Toolbox()
        self._is_maximization = is_maximization
        self._with_multi_processing = with_multi_processing

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

        if self._with_multi_processing:
            self._pool = multiprocessing.Pool(processes=15)
            self._toolbox.register("map", self._pool.map)


    # Crossover function to create two children elements based on two parents
    def crossover(self, ind1, ind2):
        size = len(ind1)
        cxpoint1 = random.randint(0, size - 1)
        cxpoint2 = random.randint(0, size - 1)

        temp1 = ind1
        temp2 = ind2

        if cxpoint1 > cxpoint2:
            cxpoint1, cxpoint2 = cxpoint2, cxpoint1

        for i in range(cxpoint1, cxpoint2 + 1):
            tmp1 = temp1[i]
            tmp2 = temp2[i]
            temp1[i] = tmp2
            temp2[i] = tmp1

        # Apply the adjustment to ensure the sums are max fleet size
        self.adjust_to_total(temp1, self._max_fleet_size)
        self.adjust_to_total(temp2, self._max_fleet_size)

        logging.info(f'Crossover of: {ind1} {ind2}',
                     extra={"clazz": self.__class__.__name__, "oid": ""})

        # Replace original individuals
        ind1[:], ind2[:] = temp1, temp2

        logging.info(f'To: {ind1} {ind2}',
                     extra={"clazz": self.__class__.__name__, "oid": ""})
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
        logging.info(f'Call Mutate: {type(individual)}',
                        extra={"clazz": self.__class__.__name__, "oid": ""})
        logging.info(f'Call Mutate: {individual}',
                        extra={"clazz": self.__class__.__name__, "oid": ""})

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

        logging.info(f'Mutate: {individual}',
                        extra={"clazz": self.__class__.__name__, "oid": ""})
        return individual,

    def save_checkpoint(self, population, halloffame, stats, gen, filename):
        cp = dict(population=population, halloffame=halloffame, stats=stats, generation=gen)
        with open(filename, "wb") as cp_file:
            pickle.dump(cp, cp_file)

    def load_checkpoint(self, filename):
        with open(filename, "rb") as cp_file:
            cp = pickle.load(cp_file)
        return cp['population'], cp['halloffame'], cp['stats'], cp['generation']

    def save_hof(self, halloffame, filename):
        cp = dict(halloffame=halloffame)
        with open(filename, "wb") as cp_file:
            pickle.dump(cp, cp_file)

    def load_hof(self, filename):
        with open(filename, "rb") as cp_file:
            cp = pickle.load(cp_file)
        return cp['halloffame']

    def get_xlsx_files(self, directory):
        xlsx_files = [f for f in os.listdir(directory) if f.endswith('.xlsx')]
        return xlsx_files

    def extract_variables(self, filename):
        pattern = r'tran_c_(\d+)_s_(\d+)_ks_(\d+)_b_(\d+)_res_(.+)\.xlsx'
        match = re.match(pattern, filename)

        if match:
            car = match.group(1)
            scooter = match.group(2)
            kick_scooter = match.group(3)
            bike = match.group(4)
            res = match.group(5)

            res = res.replace("p", ".")
            res = float(res)

            return car, scooter, kick_scooter, bike, res
        else:
            return None

    # TODO Add checkpoint
    # TODO add lo
    def optimize(self, population_size, num_generations, current_sim_id, checkpoint=None, recover_path=None):
        print(checkpoint)
        print(recover_path)

        os.makedirs(f'data/output/simulation_logs/{current_sim_id}/final', exist_ok=True)
        verbose = True
        cxpb = 0.5
        mutpb = 0.5

        recovered_values = None

        if checkpoint is not None and recover_path is None:
            pop, hof, stats, start_gen = self.load_checkpoint(checkpoint)
            print('check-----')
            print(pop, hof, stats, start_gen)
            history = tools.Statistics(lambda ind: ind)
            history.register('hof', lambda pop: hof[0])
            mstats = tools.MultiStatistics(fitness=stats, history=history)

            logbook = tools.Logbook()
            logbook.header = ['gen', 'nevals'] + (mstats.fields if mstats else [])


        elif checkpoint is None and recover_path is not None:
            old_gen = re.search(r'gen_(\d+)/', recover_path)
            old_gen = int(old_gen.group(1))

            pop = self._toolbox.population(n=population_size)
            offspring = pop

            if old_gen != 0:
                hod_path = str(recover_path).replace(f'gen_{old_gen}/transactions', f'gen_{old_gen-1}/checkpoint')
                hof = self.load_hof(f"{hod_path}/gen_{old_gen-1}_hof.pkl")
            else:
                hof = tools.HallOfFame(1)

            stats = tools.Statistics(get_fitness_values)
            stats.register("avg", np.mean)
            stats.register("min", np.min)
            stats.register("max", np.max)
            start_gen = old_gen - 1
            history = tools.Statistics(lambda ind: ind)
            history.register('hof', lambda pop: hof[0])
            mstats = tools.MultiStatistics(fitness=stats, history=history)

            logbook = tools.Logbook()
            logbook.header = ['gen', 'nevals'] + (mstats.fields if mstats else [])
            recovered_values = []
            xlsx_files = self.get_xlsx_files(recover_path)
            
            for file in xlsx_files:
                recovered_values.append(self.extract_variables(file))

        elif checkpoint is not None and recover_path is not None:
            recovered_values = []
            pop, hof, stats, start_gen = self.load_checkpoint(checkpoint)
            xlsx_files = self.get_xlsx_files(recover_path)

            history = tools.Statistics(lambda ind: ind)
            history.register('hof', lambda pop: hof[0])
            mstats = tools.MultiStatistics(fitness=stats, history=history)
            logbook = tools.Logbook()
            logbook.header = ['gen', 'nevals'] + (mstats.fields if mstats else [])

            offspring = pop

            for file in xlsx_files:
                recovered_values.append(self.extract_variables(file))
        else:
            pop = self._toolbox.population(n=population_size)
            hof = tools.HallOfFame(1)
            stats = tools.Statistics(get_fitness_values)
            stats.register("avg", np.mean)
            stats.register("min", np.min)
            stats.register("max", np.max)
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_0', exist_ok=True)
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_0/transactions', exist_ok=True)
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_0/checkpoint', exist_ok=True)
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
                self.save_hof(hof, f"data/output/simulation_logs/{current_sim_id}/gen_{0}/checkpoint/gen_{0}_hof.pkl")

            record = mstats.compile(pop) if mstats else {}
            logbook.record(gen=start_gen, nevals=len(invalid_ind), **record)
            if verbose:
                logging.info(logbook.stream,
                        extra={"clazz": self.__class__.__name__, "oid": ""})

            self.save_checkpoint(pop, hof, stats, 0,
                                 f"data/output/simulation_logs/{current_sim_id}/gen_{0}/checkpoint/gen_{0}.pkl")


        # Begin the generational process
        for gen in range(start_gen+1, num_generations + 1):
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_{gen}', exist_ok=True)
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_{gen}/transactions', exist_ok=True)
            os.makedirs(f'data/output/simulation_logs/{current_sim_id}/gen_{gen}/checkpoint', exist_ok=True)

            if recover_path is None:
                # Select the next generation individuals
                offspring = self._toolbox.select(pop, len(pop))

                # Vary the pool of individuals
                offspring = varAnd(offspring, self._toolbox, cxpb, mutpb)

                # Evaluate the individuals with an invalid fitness, create a tuple of ind and gen
                # TODO: Idea for making it parallelizeable, [(ind, gen) for ind in offspring if not ind.fitness.valid]
                invalid_ind = [(ind, gen) for ind in offspring if not ind.fitness.valid]

                # Store the number of planned evals for debug
                open(f"data/output/simulation_logs/{current_sim_id}/gen_{gen}/neval_{len(invalid_ind)}.txt", "x")

                fitnesses = self._toolbox.map(self._toolbox.evaluate, invalid_ind)

                logging.info("Finished evaluation",
                             extra={"clazz": self.__class__.__name__, "oid": ""})

                for ind, fit in zip(invalid_ind, fitnesses):
                    ind[0].fitness.values = fit
            else:
                new_offspring = []

                print('recovered_values', recovered_values)
                for evals in recovered_values:
                    print('evals', evals)

                    car, scooter, kick_scooter, bike, res = evals
                    logging.info(f'evals {car, scooter, kick_scooter, bike, res}',
                                 extra={"clazz": self.__class__.__name__, "oid": ""})

                    ind = copy.deepcopy(offspring[0])

                    ind[0] = int(car)
                    ind[1] = int(scooter)
                    ind[2] = int(kick_scooter)
                    ind[3] = int(bike)

                    ind.fitness.values = (res,)

                    new_offspring.append(ind)

                recover_path = None
                offspring = new_offspring
                invalid_ind = [(ind, gen) for ind in offspring if not ind.fitness.valid]

            # Update the hall of fame with the generated individuals
            if hof is not None:
                hof.update(offspring)
                self.save_hof(hof,
                              f"data/output/simulation_logs/{current_sim_id}/gen_{gen}/checkpoint/gen_{gen}_hof.pkl")

            # Replace the current population by the offspring
            pop[:] = offspring

            # Append the current generation statistics to the logbook
            record = mstats.compile(pop) if mstats else {}
            logbook.record(gen=gen, nevals=len(invalid_ind), **record)

            logging.info("logbook-------",
                        extra={"clazz": self.__class__.__name__, "oid": ""})
            logging.info(logbook,
                        extra={"clazz": self.__class__.__name__, "oid": ""})

            logging.info("hof-------",
                        extra={"clazz": self.__class__.__name__, "oid": ""})
            logging.info(hof,
                        extra={"clazz": self.__class__.__name__, "oid": ""})

            if verbose:
                logging.info(logbook.stream,
                        extra={"clazz": self.__class__.__name__, "oid": ""})

            df_log = pd.DataFrame(logbook.chapters["history"])
            df_log.to_excel(f'data/output/simulation_logs/{current_sim_id}/ea_alg_metrics.xlsx')

            # Save checkpoint of current generation
            self.save_checkpoint(pop, hof, stats, gen, f"data/output/simulation_logs/{current_sim_id}/gen_{gen}/checkpoint/gen_{gen}.pkl")

        logging.info("End of Optimization",
                        extra={"clazz": self.__class__.__name__, "oid": ""})
        logging.info(f'Best Solution: {hof[0]} Relative Revenue: {hof[0].fitness.values[0]}',
                        extra={"clazz": self.__class__.__name__, "oid": ""})
        logging.info(logbook.chapters["fitness"].select("gen"),
                        extra={"clazz": self.__class__.__name__, "oid": ""})
        self._pool.close()

