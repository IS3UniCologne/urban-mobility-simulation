import logging
import random

import numpy as np
from numpy.random import PCG64, Generator

from simulation.helper.configuration.configuration import Configuration
from simulation.helper.singleton import Singleton


class RandomManager(metaclass=Singleton):
    """
    Singleton class to manage random number generation throughout the simulation.
    Ensures reproducibility when using the same seed and configuration.

    Each simulation component can have its own random number generator to avoid interference between components.
    There is also a main RNG that is used by default if no component-specific RNG is requested.

    To use the RandomManager, call the get_rng() method with the name of the component that needs random numbers.
    If no component name is provided, the main RNG is returned.
    The RNG can then be used to generate random numbers using the methods provided by NumPy's Generator class.

    Example:
    ```
    random_manager = RandomManager()
    rng = random_manager.get_rng("SIMULATIONCOMPONENT")
    random_number = rng.uniform(0, 1)
    ```

    The RandomManager also provides a set of convenience methods for generating random numbers directly.
    These methods are thin wrappers around the corresponding NumPy methods.
    Use them when you don't need to keep the RNG instance around.

    Example:
    ```
    random_manager = RandomManager()
    random_number = random_manager.uniform(0, 1, component="OTHERSIMULATIONCOMPONENT")
    ```
    """

    def __init__(self) -> None:
        self._main_seed = None
        self._main_rng = None
        self._fixed_seed_components = None
        self._component_rngs = {}
        self.reset_rng()

    def reset_fixed_seed_components(self) -> None:
        """Reset the fixed seed components' generators to their initial state."""

        self._fixed_seed_components = None
        self._fixed_seed_components = (
            Configuration().random_manager.COMPONENT_SEEDS.copy()
        )

        for component, seed in self._fixed_seed_components.items():
            if seed == 0:
                self._fixed_seed_components[component] = (
                    np.random.SeedSequence().entropy % 2**32
                )
            self._create_component_rng(
                component, self._fixed_seed_components[component]
            )

    def reset_rng(self) -> None:
        """Resets all random number generators to their inital state (same as restarting the simulation)."""
        self._main_seed = None
        self._main_rng = None
        self._component_rngs = {}

        self.reset_fixed_seed_components()

        main_seed = Configuration().random_manager.SEED
        # If the seed is 0, we use a random seed
        if main_seed == 0:
            main_seed = np.random.SeedSequence().entropy % 2**32

        self._main_seed = main_seed

        # Use the PCG64 generator in case the default changes in the future
        self._main_rng = np.random.Generator(PCG64(main_seed))

        # Also set the global seeds in case any libaries use them
        np.random.seed(main_seed)
        random.seed(main_seed)

        logging.info(
            f"Random seed set to {main_seed}",
            extra={"clazz": "RandomManager", "oid": ""},
        )

    def get_rng(self, component_name: str = None) -> Generator:
        """
        Get a random number generator for a specific component.
        If no component name is provided, returns the main RNG.
        If the generator for the component does not exist, it is created.

        Returns:
            np.random.Generator: A NumPy Generator instance
        """
        if component_name is None:
            return self._main_rng

        if component_name not in self._component_rngs:
            self._create_component_rng(component_name)

        return self._component_rngs[component_name]

    def _create_component_rng(
        self, component_name: str, component_seed: int = None
    ) -> None:
        """Create a new random number generator for a specific component."""
        if component_seed is None:
            component_seed = self._generate_component_seed(component_name)
        self._component_rngs[component_name] = np.random.Generator(
            PCG64(component_seed)
        )
        logging.info(
            f"New RNG created for component {component_name} with seed {component_seed} ",
            extra={"clazz": "RandomManager", "oid": ""},
        )
        return

    def _generate_component_seed(self, component_name: str) -> int:
        """Create a deterministic seed for a component based on the main seed and component name."""
        if self._main_seed is None:
            raise ValueError("Main seed must be set before creating component RNGs")

        # Simple deterministic hash function
        # Python's built in hash function is not deterministic, so we do this instead :)
        hash_value = 0
        for char in component_name:
            hash_value = (hash_value * 31 + ord(char)) & 0xFFFFFFFF

        return (self._main_seed + hash_value) % 2**32

    # Random sampling methods, these are just thin wrappers around NumPy's Generator methods
    # They can be called directly on the RandomManager instance without needing to get the RNG first

    def uniform(
        self,
        low: float = 0.0,
        high: float = 1.0,
        size: None | int | tuple[int, ...] = None,
        component: None | str = None,
    ) -> float | np.ndarray:
        """Generate uniform random numbers between low and high."""
        rng = self.get_rng(component)
        return rng.uniform(low, high, size=size)

    def integers(
        self,
        low: int,
        high: int,
        size: None | int | tuple[int, ...] = None,
        component: None | str = None,
    ) -> int | np.ndarray:
        """Generate random integers from low (inclusive) to high (exclusive)."""
        rng = self.get_rng(component)
        return rng.integers(low, high, size=size)
