import numpy as np
import pytest

# we have to set sys argv before importing Configuration
from simulation.helper.configuration.configuration import Configuration
from simulation.helper.random.random_manager import RandomManager


# Test component seed generation
def test_component_seed_generation():  # noqa: ANN201
    seed1 = RandomManager()._generate_component_seed("test_component")  # noqa: SLF001
    seed2 = RandomManager()._generate_component_seed("test_component")  # noqa: SLF001
    assert seed1 == seed2, "Component seeds should be the same for the same component"
    assert seed1 != RandomManager()._generate_component_seed("different_component"), (  # noqa: SLF001
        "Component seeds should be different for different components"
    )


# Test get_rng functionality
def test_get_rng_default():  # noqa: ANN201
    """Test that get_rng() returns the main RNG when no component is specified."""
    random_manager = RandomManager()

    # Check that default RNG is the main RNG
    assert random_manager.get_rng() is random_manager._main_rng  # noqa: SLF001

    # Check that multiple calls return the same RNG
    assert random_manager.get_rng() is random_manager.get_rng()


def test_get_rng_component():  # noqa: ANN201
    """Test that get_rng creates and returns component-specific RNGs."""
    random_manager = RandomManager()

    # Getting a component RNG should create a new one
    component_name = "test_component"
    rng = random_manager.get_rng(component_name)

    # Should be in the component RNGs dictionary
    assert component_name in random_manager._component_rngs  # noqa: SLF001
    assert random_manager._component_rngs[component_name] is rng  # noqa: SLF001

    # Multiple calls should return the same RNG instance
    assert random_manager.get_rng(component_name) is rng


def test_rng_reproducibility():  # noqa: ANN201
    """Test that RNGs with the same seed produce the same sequence of numbers."""
    # Set a specific seed
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 42)
    random_manager.reset_all_rng()

    # Generate some random numbers
    numbers1 = [random_manager.uniform() for _ in range(10)]

    # Reset the seed and generate again
    random_manager.reset_all_rng()
    numbers2 = [random_manager.uniform() for _ in range(10)]

    # Should get exactly the same sequence
    np.testing.assert_array_equal(numbers1, numbers2)


def test_component_rng_reproducibility():  # noqa: ANN201
    """Test that component RNGs with the same seed produce the same sequence."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 42)
    random_manager.reset_all_rng()

    component = "test_component"

    # Generate some random numbers with a component
    numbers1 = [random_manager.uniform(component=component) for _ in range(10)]

    # Reset and try again
    random_manager.reset_all_rng()
    numbers2 = [random_manager.uniform(component=component) for _ in range(10)]

    # Should get exactly the same sequence
    np.testing.assert_array_equal(numbers1, numbers2)


def test_different_components_different_sequences():  # noqa: ANN201
    """Test that different components get different random sequences."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 42)
    random_manager.reset_all_rng()

    # Generate numbers from two different components
    component1 = "component_1"
    component2 = "component_2"

    numbers1 = [random_manager.uniform(component=component1) for _ in range(10)]
    numbers2 = [random_manager.uniform(component=component2) for _ in range(10)]

    # Should NOT be the same sequence
    with pytest.raises(AssertionError):
        np.testing.assert_array_equal(numbers1, numbers2)


def test_component_independence():  # noqa: ANN201
    """Test that component RNGs are independent of each other."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 42)
    random_manager.reset_all_rng()

    component1 = "component_1"
    component2 = "component_2"

    # Generate from component1
    numbers1_before = [random_manager.uniform(component=component1) for _ in range(5)]

    # Generate from component2
    [random_manager.uniform(component=component2) for _ in range(10)]

    # Generate more from component1
    numbers1_after = [random_manager.uniform(component=component1) for _ in range(5)]

    # Reset and generate just from component1
    random_manager.reset_all_rng()
    expected_numbers = [random_manager.uniform(component=component1) for _ in range(10)]

    # The component1 sequence should be unaffected by component2 usage
    np.testing.assert_array_equal(numbers1_before + numbers1_after, expected_numbers)


def test_seed_zero():  # noqa: ANN201
    """Setting the seed to zero should lead to a random seed being generated."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 0)
    random_manager.reset_all_rng()

    # Should not be zero
    main_seed1 = random_manager._main_seed  # noqa: SLF001
    assert main_seed1 != 0

    # Resetting the seed should give a different random seed
    random_manager.reset_all_rng()
    main_seed2 = random_manager._main_seed  # noqa: SLF001
    assert main_seed2 != 0
    assert main_seed1 != main_seed2


def test_uniform():  # noqa: ANN201
    """Test that the uniform method returns values between 0 and 1."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 42)
    random_manager.reset_all_rng()

    # Generate some random numbers
    numbers = [random_manager.uniform() for _ in range(1000)]

    # All numbers should be between 0 and 1
    assert all(0 <= x <= 1 for x in numbers)

    # Check that the seed is used
    random_manager.reset_all_rng()
    numbers2 = [random_manager.uniform() for _ in range(1000)]
    assert np.allclose(numbers, numbers2), (
        "The same seed should produce the same sequence of random numbers"
    )

    # What about different seeds?
    object.__setattr__(Configuration().random_manager, "SEED", 43)
    random_manager.reset_all_rng()
    numbers3 = [random_manager.uniform() for _ in range(1000)]
    assert not np.allclose(numbers, numbers3), (
        "Different seeds should produce different sequences of random numbers"
    )


def test_component_seed_zero() -> None:
    """Setting the component seed to zero should lead to different results on each reset."""
    random_manager = RandomManager()
    object.__setattr__(Configuration().random_manager, "SEED", 0)
    random_manager.reset_all_rng()

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
