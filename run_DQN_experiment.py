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
    # define experiments with kwargs
    experiments = [
        {'penalty': 100},
        {'penalty': 90},
        {'penalty': 80},
        {'penalty': 70},
        {'penalty': 60},
        {'penalty': 50},
        {'penalty': 40},
        {'penalty': 30},
        {'penalty': 20},
        {'penalty': 10}
    ]

    # or just run average experiments by using range with the number you like
    # experiments = range(10)

    # only use physical cores
    results = pqdm(experiments,
                   run,
                   argument_type='kwargs',
                   n_jobs=min(psutil.cpu_count(logical=False), len(experiments)),
                   mp_context=mp.get_context('spawn'))

    if type(experiments) is range:
        # compute and plot average returns

        collected = pd.concat(results).groupby('episode').mean()
        collected.plot(ylabel='average return', legend=False, title=f'{str(len(results))} Experiments averaged returns')
        plt.show()
    else:
        # don't plot, is plotted individually in run function
        collected = pd.concat(results)
        # collected.plot(by='penalty', legend=True)

    if type(experiments) is range:
        collected.to_csv(
            os.path.join(
                output_folder,
                f'average_{str(len(experiments))}_experiments_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}'
            )
        )
    else:
        collected.to_csv(
            os.path.join(
                output_folder,
                f'search_{list(experiments[0])[0]}_experiments_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}'
            )
        )
