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
from main_transit import run

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
    
    Constrained by memory: A full (100,000) replay buffer takes about 31GB or RAM.
    """

    # define experiments with kwargs
    experiments = [
        {'penalty': 0},
        {'penalty': 5},
        {'penalty': 10},
        {'penalty': 15},
        {'penalty': 20}
    #     {'penalty': 25},
    #     {'penalty': 25},
    #     {'penalty': 20},
    #     {'penalty': 20},
    #     {'penalty': 15},
    #     {'penalty': 15}
    ]

    # experiments = [
    #     {'q_net_layer': (32,32)},
    #     {'q_net_layer': (32,16)},
    #     {'q_net_layer': (64, 32)},
    #     {'q_net_layer': (64, 16)},
    #     {'q_net_layer': (16, 16)},
    #     {'q_net_layer': (16, 8)}
    # ]

    # or just run average experiments by using range with the number you like
    # experiments = range(5)

    if type(experiments) is range:
        results = pqdm(experiments,
                       run,
                       n_jobs=min(psutil.cpu_count(logical=False), len(experiments)),
                       mp_context=mp.get_context('spawn'))

        # compute and plot average returns
        path = f'average_{str(len(experiments))}_experiments_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'

        collected = pd.concat(results).groupby('episode').mean()
        collected.plot(secondary_y=['service_level'],
                       alpha=.5,
                       color=['black', 'green'],
                       title=f'{str(len(results))} Experiments averaged Returns and Service Level')
        plt.show()
    else:
        results = pqdm(experiments,
                       run,
                       argument_type='kwargs',
                       n_jobs=min(psutil.cpu_count(logical=False), len(experiments)),
                       mp_context=mp.get_context('spawn'))

        path = f'search_{list(experiments[0])[0]}_experiments_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'

        # don't plot, is plotted individually in run function
        collected = pd.concat(results)
        # collected.plot(by='penalty', legend=True)

    collected.to_csv(
        os.path.join(
            output_folder,
            path
        )
    )
