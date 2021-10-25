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
    """

    # define experiments with kwargs
    # experiments = [
    #     {'penalty': 45},
    #     {'penalty': 45},
    #     {'penalty': 40},
    #     {'penalty': 40},
    #     {'penalty': 35},
    #     {'penalty': 35},
    #     {'penalty': 30},
    #     {'penalty': 30},
    #     {'penalty': 25},
    #     {'penalty': 25}
    # ]

    # or just run average experiments by using range with the number you like
    experiments = range(10)

    if type(experiments) is range:
        results = pqdm(experiments,
                       run,
                       n_jobs=min(psutil.cpu_count(logical=False), len(experiments)),
                       mp_context=mp.get_context('spawn'))

        # compute and plot average returns
        path = f'average_{str(len(experiments))}_experiments_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.csv'

        collected = pd.concat(results).groupby('episode').mean()
        collected.plot(ylabel='average return', legend=False, title=f'{str(len(results))} Experiments averaged returns')
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
