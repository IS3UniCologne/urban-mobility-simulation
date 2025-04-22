import sys
from unittest.mock import PropertyMock, patch

import numpy as np
import pytest

sys.argv = [
    sys.argv[0],
    "resources/configurations/config_template.toml",
]  # Add a path to a test config file

# we have to set sys argv before importing Configuration
from simulation.helper.configuration.configuration import (  # noqa: E402
    Configuration,
    RandomManagerConfig,
)
from simulation.helper.random.random_manager import RandomManager  # noqa: E402


# Test component seed generation
def test_component_seed_generation():
    seed1 = RandomManager()._generate_component_seed("test_component")
    seed2 = RandomManager()._generate_component_seed("test_component")
    assert seed1 == seed2, "Component seeds should be the same for the same component"
    assert seed1 != RandomManager()._generate_component_seed("different_component"), (
        "Component seeds should be different for different components"
    )


# Test get_rng functionality
def test_get_rng_default():
    """Test that get_rng() returns the main RNG when no component is specified."""
    random_manager = RandomManager()

    # Check that default RNG is the main RNG
    assert random_manager.get_rng() is random_manager._main_rng

    # Check that multiple calls return the same RNG
    assert random_manager.get_rng() is random_manager.get_rng()


def test_get_rng_component():
    """Test that get_rng creates and returns component-specific RNGs."""
    random_manager = RandomManager()

    # Getting a component RNG should create a new one
    component_name = "test_component"
    rng = random_manager.get_rng(component_name)

    # Should be in the component RNGs dictionary
    assert component_name in random_manager._component_rngs
    assert random_manager._component_rngs[component_name] is rng

    # Multiple calls should return the same RNG instance
    assert random_manager.get_rng(component_name) is rng


def test_rng_reproducibility():
    """Test that RNGs with the same seed produce the same sequence of numbers."""
    # --- 1. Prepare the Test-Specific RNG Config ---
    # Create a *new*, real RandomManagerConfig instance just for this test.
    # Because we create it here, we can set the seed during initialization.
    # This respects the frozen=True nature after creation.
    test_rng_config = RandomManagerConfig(
        SEED=42,
        COMPONENT_SEEDS={
            "POPULATIONFACTORY": 42,
            "FLEETFACTORY": 42,
            "DEMANDFACTORY": 42,
            "INITIALSOC": 42,
            "GEOENV": 42,
        },
    )

    # --- 2. Patch the 'random_manager' Property on the Configuration Class ---
    # We use patch.object to target the 'random_manager' attribute
    # specifically on the Configuration *class*.
    # 'new_callable=PropertyMock' tells patch to replace it with a PropertyMock.
    # 'return_value=test_rng_config' configures this PropertyMock.
    with patch.object(
        Configuration,  # Target the Configuration class
        "random_manager",  # The name of the property
        new_callable=PropertyMock,  # Replace with a PropertyMock
        return_value=test_rng_config,  # Make it return our test config
    ) as mock_prop:
        # --- 3. Execute Test Logic within the patched context ---

        # Inside this 'with' block:
        # - Accessing Configuration().random_manager will now execute our
        #   PropertyMock and immediately return test_rng_config.
        # - Accessing Configuration().random_manager.SEED will return 42.

        # Instantiate or get the RandomManager Singleton
        # (Its actual instantiation doesn't matter as much now, as long
        # as reset_rng uses the patched property access)
        test_manager = RandomManager()

        # Call the function under test.
        # The line 'main_seed = Configuration().random_manager.SEED' inside
        # reset_rng will now effectively become 'main_seed = test_rng_config.SEED',
        # yielding 42.
        test_manager.reset_rng()

        # Generate some random numbers
        numbers1 = [test_manager.uniform() for _ in range(10)]

        # Reset the seed and generate again
        test_manager.reset_rng()
        numbers2 = [test_manager.uniform() for _ in range(10)]

        # Should get exactly the same sequence
        np.testing.assert_array_equal(numbers1, numbers2)


def test_component_rng_reproducibility():
    """Test that component RNGs with the same seed produce the same sequence."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 42)
    random_manager.reset_rng()

    component = "test_component"

    # Generate some random numbers with a component
    numbers1 = [random_manager.uniform(component=component) for _ in range(10)]

    # Reset and try again
    random_manager.reset_rng()
    numbers2 = [random_manager.uniform(component=component) for _ in range(10)]

    # Should get exactly the same sequence
    np.testing.assert_array_equal(numbers1, numbers2)


def test_different_components_different_sequences():
    """Test that different components get different random sequences."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 42)
    random_manager.reset_rng()

    # Generate numbers from two different components
    component1 = "component_1"
    component2 = "component_2"

    numbers1 = [random_manager.uniform(component=component1) for _ in range(10)]
    numbers2 = [random_manager.uniform(component=component2) for _ in range(10)]

    # Should NOT be the same sequence
    with pytest.raises(AssertionError):
        np.testing.assert_array_equal(numbers1, numbers2)


def test_component_independence():
    """Test that component RNGs are independent of each other."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 42)
    random_manager.reset_rng()

    component1 = "component_1"
    component2 = "component_2"

    # Generate from component1
    numbers1_before = [random_manager.uniform(component=component1) for _ in range(5)]

    # Generate from component2
    [random_manager.uniform(component=component2) for _ in range(10)]

    # Generate more from component1
    numbers1_after = [random_manager.uniform(component=component1) for _ in range(5)]

    # Reset and generate just from component1
    random_manager.reset_rng()
    expected_numbers = [random_manager.uniform(component=component1) for _ in range(10)]

    # The component1 sequence should be unaffected by component2 usage
    np.testing.assert_array_equal(numbers1_before + numbers1_after, expected_numbers)


def test_seed_zero():
    """Setting the seed to zero should lead to a random seed being generated."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 0)
    random_manager.reset_rng()

    # Should not be zero
    main_seed1 = random_manager._main_seed
    assert main_seed1 != 0

    # Resetting the seed should give a different random seed
    random_manager.reset_rng()
    main_seed2 = random_manager._main_seed
    assert main_seed2 != 0
    assert main_seed1 != main_seed2


def test_uniform():
    """Test that the uniform method returns values between 0 and 1."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 42)
    random_manager.reset_rng()

    # Generate some random numbers
    numbers = [random_manager.uniform() for _ in range(1000)]

    # All numbers should be between 0 and 1
    assert all(0 <= x <= 1 for x in numbers)

    # Check that the seed is used
    random_manager.reset_rng()
    numbers2 = [random_manager.uniform() for _ in range(1000)]
    assert np.allclose(numbers, numbers2), (
        "The same seed should produce the same sequence of random numbers"
    )

    # What about different seeds?
    object.__setattr__(Configuration().random_manager, "SEED", 43)
    random_manager.reset_rng()
    numbers3 = [random_manager.uniform() for _ in range(1000)]
    assert not np.allclose(numbers, numbers3), (
        "Different seeds should produce different sequences of random numbers"
    )


def test_component_seed_zero() -> None:
    """Setting the component seed to zero should lead to different results on each reset."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 0)
    random_manager.reset_rng()

    component = "TESTCOMPONENT"
    Configuration().random_manager.COMPONENT_SEEDS[component] = 0
    random_manager.reset_fixed_seed_components()

    # Store first sequence of random numbers to compare later
    sequence1 = [random_manager.uniform(component=component) for _ in range(5)]

    # Resetting the seed should give a different random seed
    random_manager.reset_fixed_seed_components()

    # Generate new sequence with reset RNG
    sequence2 = [random_manager.uniform(component=component) for _ in range(5)]

    # The sequences should be different since the seed should be randomly generated each time
    with pytest.raises(AssertionError):
        np.testing.assert_array_equal(sequence1, sequence2)
        np.testing.assert_array_equal(sequence1, sequence2)
