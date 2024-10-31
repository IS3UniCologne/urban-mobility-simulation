# urban-mobility-simulation
[![develop - ruff-fix.yml](https://github.com/IS3UniCologne/urban-mobility-simulation/actions/workflows/ruff-fix.yml/badge.svg?branch=develop)](https://github.com/IS3UniCologne/urban-mobility-simulation/actions/workflows/ruff-fix.yml)

We provide a simulation platform considering shared mobility (ride sharing, vehicle sharing) services along with infrastructure services (e.g., charging)

## Setup
> Before doing anything else, set `conda config --set channel_priority strict` to avoid common mixed-channel pitfalls.

* Because this simulation requires a lot of dependencies, using a conda environment created by `conda env create -f ./resources/environment/environment.yml` is highly recommended.
* Because we want to support as many platforms as possible, we need to stick to certain Python versions as defined in `environment.yml`.
Other Python versions are untested!

## Running an experiment
> We provide templates (`*_template.py`) for most common use cases, please refer to this!
> At the moment, `template_all_modes.py` is not working, we first need to fix several issues for true multi-modal users.

Provide configuration files as the first argument after the experiment file name such as `python experiment_template.py ./resources/configurations/template.ini`

## Simulation Components
> The simulation consists of three different types of mobility services: 
- *public transport (currently only busses)*
- *ride-hailing fleet (autonomous vehicles and ride-hailing cars)*
- *shared mobility fleet (Cars, scooters, kickscooters and bikes)*

The configurations of these fleets and their operator modules together with other components such as the charging infrastructure, spatial/temporal resolution and world are initialized with the information set in the `template.ini`

This file is used to set various parameters in the following blocks that are required in every simulation:

- **Experiment Management**:
  Contains the **start and end time** of the simulation and additionally a **seed**.

- **World Resolution**:
    Contains the **spatial, temporal and daily resolution** and the city to be simulated.

- **Input Files**:
    Loads files regarding **demand, supply, supply probability, transit timetable (for the busses) and environment** (layers for different resolutions).

- **Public Operator Configuration**:
    Initializes the **User and TransitOperator** configurations with variables such as the **max number of busses** and **maximum waiting time** of a user.

- **Shared Vehicle Fleet Configuration**:
    Initializes the **Shared Vehicle and Shared Vehicle Operator** configuratons with variables such as **energy consumptions, prices and initial SoCs** belonging to different vehicle types and the **base regions** in which **service workers** of the Operator are active.

- **RideHailing Fleet Configuration**:
    Initializes RideHailing Operator and several other configurations with variables such as **energy consumptions, prices and initial SoCs** belonging to different vehicle types and the **base regions** in which **service workers** of the Operator are active. There are also only ridehailing specific variables such as the **driver payment share**.

- **Charging Infrastructure**:
    Contains charging configurations such as the **charging power and capacity of the charging stations**. Initializes the Charging Infrastructure configuration.

- **Output Configuration**:
    Initiliazes the Global configuration with parameters required for output management such as the path for the **output/transactions files**

- **Logging**:
    Initializes a **basic configuration** for logging outputs and adds **custom filters** to these.

- **Loading Demand Data and Distance Matrix**:
    Estimates demand regarding arrival times and origin destinations in spatio-temporal resolution and calculates a matrix with the distances between hexagons. 

- **Simulation Modules**:
    - Initialize the **search** (helps users search for vehicles), **payment** (manages the transactions at the end of each trip) and **vehicle assignment** (assigns the chosen vehicle to the user) engines. Currently all fleets use their own engines.
    - Generate the fleets  and their respective configuration files.
    - Initialize the respective **operators** of the fleets (PublicTransitOperator,OperationsRideHailing and Operations). 
    - Ridehailing and shared mobility fleets also get **scheduler modules** for the planning of their charging schedules and the relocations of the vehicles (RebalancingScheduler and RelocationScheduler).
    - Initiliaze **task queues** and **service workers** for ridehailing and shared mobility fleets. Service workers are assigned these tasks to move the vehicles to the charging stations or relocate them.
    - Initialize **world** with the engines, charging infrastructure and **population factory**.
    - Start spawning demand processes with the **demand factory**.
    - Run the simulation until *end_time*.
    



## Pull Requests

All pull requests must conform in formatting and linting to the interpretation of *ruff* on *blacks* code style and to the PEP definitions and their interpretation. In case a pull request's check of the *ruff* style fails, you have to run ruff locally. Simply use the following command:
```
ruff check .
```
In the output, you can see what exactly is causing the problems. In order for the pull request to pass, you need to fix all issues and commit the changes to your pull request. After that, the code checks should complete successfully.

You can use ruff to format your code as well. In that case, use the following command:
```
ruff format
```


