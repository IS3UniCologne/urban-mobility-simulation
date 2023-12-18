# urban-mobility-simulation
We provide a simulation platform considering shared mobility (ride sharing, vehicle sharing) services along with infrastructure services (e.g., charging)

## Setup
> Before doing anything else, set `conda config --set channel_priority strict` to avoid common mixed-channel pitfalls.

* Because this simulation requires a lot of dependencies, using a conda environment created by `conda env create -f ./resources/environment/environment.yml` is highly recommended.
* Because we want to support as many platforms as possible, we need to stick to certain Python versions as defined in `environment.yml`.
Other Python versions are untested!
> If you are on newer Macs (Apple Silicon) please use `environment_mac.yml` with special tensorflow dependencies!

## Running an experiment
> We provide a template at `experiment_template.py` for most common use cases, please refer to this!

Provide configuration files as the first argument after the experiment file name such as `python experiment_template.py ./resources/configurations/app-remote.ini`