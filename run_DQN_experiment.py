import datetime
import os
import sys
from configparser import ConfigParser
from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt
from pqdm.processes import pqdm
from main_transit import run

# Change working directory to path of this file
working_dir = Path(__file__).parent
os.chdir(working_dir)

# Read args
parser = ConfigParser()
parser.read(sys.argv[1])

output_folder = parser.get("OUTPUT", "output_folder")

if __name__ == "__main__":
    experiments = range(10)

    # results = pqdm(experiments, run, n_jobs=min(12, len(experiments))) # Remote Ryzen 12core
    results = pqdm(experiments, run, n_jobs=min(4, len(experiments))) # Local i7 4core

    collected = pd.concat(results).groupby('episode').mean()
    collected.plot(ylabel='average return', legend=False, title=f'{str(len(results))} Experiments averaged returns')
    plt.show()
    collected.to_csv(os.path.join(output_folder,
                                  f'{str(len(experiments))} run experiment {datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}'))