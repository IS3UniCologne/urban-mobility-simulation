import datetime
import os
import sys
from configparser import ConfigParser
from pathlib import Path
import psutil

import pandas as pd
from matplotlib import pyplot as plt
from pqdm.processes import pqdm
import multiprocessing as mp
from main_transit import learn_agent

# Change working directory to path of this file
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read args
parser = ConfigParser()
parser.read(sys.argv[1])

output_folder = parser.get("OUTPUT", "output_folder")

if __name__ == "__main__":
    """
    Use number of physical cores available to run parallel experiments
    either a grid search (by kwargs, see below) or an averaging benchmark
    (by range, see below)
    
    Constrained by memory: A 100,000 experiences replay buffer takes about 31GB of RAM.
    """

    # define experiments with kwargs
    # experiments = [
    #     {'penalty': 0},
    #     {'penalty': 5},
    #     {'penalty': 10},
    #     {'penalty': 15},
    #     {'penalty': 20}
    #     {'penalty': 25},
    #     {'penalty': 25},
    #     {'penalty': 20},
    #     {'penalty': 20},
    #     {'penalty': 15},
    #     {'penalty': 15}
    # ]

    # experiments = [
    #     {'q_net_layer': (32,32)},
    #     {'q_net_layer': (32,16)},
    #     {'q_net_layer': (64, 32)},
    #     {'q_net_layer': (64, 16)},
    #     {'q_net_layer': (16, 16)},
    #     {'q_net_layer': (16, 8)}
    # ]

    # experiments = [
    #     {'q_net_layer': (22,22)},
    #     {'q_net_layer': (22,11)},
    #     {'q_net_layer': (22,)},
    #     {'q_net_layer': (11, 11)},
    #     {'q_net_layer': (11,)},
    #     {'q_net_layer': (6,)}
    # ]

    # experiments = [
    #     {'buffersize': 500},
    #     {'buffersize': 1000},
    #     {'buffersize': 250}
    # ]

    # experiments = [
    #     {'action_space': ["UP","DOWN","UP_LEFT","UP_RIGHT","DOWN_LEFT","DOWN_RIGHT"]},
    #     {'action_space': ["STAY","UP","DOWN","UP_LEFT","UP_RIGHT","DOWN_LEFT","DOWN_RIGHT"]}
    # ]

    # experiments = [
    #     {'lr_decay': True},
    #     {'lr_decay': False}
    # ]

    # how many parallel runs of each experiment should be done and then averaged?
    average_experiments = 10
    # keep raw returns of all experiments, i.e. do not average?
    keepraw = True

    # or just run average experiments by using range with the number you like
    experiments = range(10)

    if type(experiments) is range:
        results = pqdm(experiments,
                       learn_agent,
                       n_jobs=min(psutil.cpu_count(logical=False), len(experiments)),
                       mp_context=mp.get_context('spawn'))

        # compute and plot average returns
        path = f'average_{str(len(experiments))}_experiments_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'

        collected = pd.concat(results).groupby('episode', as_index=True).mean()
        collected.plot(secondary_y=['service_level'],
                       alpha=.5,
                       color=['black', 'green'],
                       title=f'{str(len(results))} Experiments averaged Returns and Service Level')
        plt.show()
    else:
        if average_experiments > 1:
            # repeat each experiment average_experiments times
            experiments = [e for e in experiments for _ in range(average_experiments)]

        results = pqdm(experiments,
                       learn_agent,
                       argument_type='kwargs',
                       n_jobs=min(psutil.cpu_count(logical=False), len(experiments)),
                       mp_context=mp.get_context('spawn'))

        if average_experiments > 1 and not keepraw:
            collected = pd.concat(results).groupby([*experiments[0].keys(), 'episode']).mean().reset_index()
            path = f'search_{list(experiments[0])[0]}_experiments_averaged_{average_experiments}_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'
        else:
            collected = pd.concat(results)
            path = f'search_{list(experiments[0])[0]}_experiments_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'

    collected.to_csv(
        os.path.join(
            output_folder,
            path
        ),
        index = True if type(experiments) is range or keepraw else False
    )
