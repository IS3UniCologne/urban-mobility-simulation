"""Unit tests for RandomManager class."""

import numpy as np
import pytest

from simulation.helper.configuration.configuration import Configuration
from simulation.helper.random.random_manager import RandomManager


@pytest.mark.unit
class TestRandomManager:
    """Unit tests for RandomManager functionality."""

    @pytest.fixture(autouse=True)
    def setup_method(self) -> None:
        """Set up test environment before each test method.

        This fixture automatically runs before each test method to ensure
        clean state and proper configuration setup.
        """
        # Reset configuration to default state
        self.original_seed = Configuration().random_manager.SEED
        self.original_component_seeds = (
            Configuration().random_manager.COMPONENT_SEEDS.copy()
        )

    def teardown_method(self) -> None:
        """Clean up after each test method.

        Restores original configuration values to prevent test interference.
        """
        # Restore original configuration
        object.__setattr__(Configuration().random_manager, "SEED", self.original_seed)
        Configuration().random_manager.COMPONENT_SEEDS.clear()
        Configuration().random_manager.COMPONENT_SEEDS.update(
            self.original_component_seeds
        )

    def test_component_seed_generation(self) -> None:
        """Test that component seeds are generated consistently and uniquely."""
        random_manager = RandomManager()

        # Same component should get same seed
        seed1 = random_manager._generate_component_seed("test_component")
        seed2 = random_manager._generate_component_seed("test_component")
        assert seed1 == seed2, (
            "Component seeds should be the same for the same component"
        )

        # Different components should get different seeds
        different_seed = random_manager._generate_component_seed("different_component")
        assert seed1 != different_seed, (
            "Component seeds should be different for different components"
        )

    def test_get_rng_default(self) -> None:
        """Test that get_rng returns the main RNG when no component is specified."""
        random_manager = RandomManager()

        # Check that default RNG is the main RNG
        assert random_manager.get_rng() is random_manager._main_rng

        # Check that multiple calls return the same RNG
        assert random_manager.get_rng() is random_manager.get_rng()

    def test_get_rng_component(self) -> None:
        """Test that get_rng creates and returns component-specific RNGs."""
        random_manager = RandomManager()
        component_name = "test_component"

        # Getting a component RNG should create a new one
        rng = random_manager.get_rng(component_name)

        # Should be in the component RNGs dictionary
        assert component_name in random_manager._component_rngs
        assert random_manager._component_rngs[component_name] is rng

        # Multiple calls should return the same RNG instance
        assert random_manager.get_rng(component_name) is rng

    def test_rng_reproducibility(self) -> None:
        """Test that RNGs with the same seed produce the same sequence of numbers."""
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

    def test_component_rng_reproducibility(self) -> None:
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

    def test_different_components_different_sequences(self) -> None:
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

    def test_component_independence(self) -> None:
        """Test that component RNGs are independent of each other."""
        random_manager = RandomManager()
        object.__setattr__(Configuration().random_manager, "SEED", 42)
        random_manager.reset_all_rng()

        component1 = "component_1"
        component2 = "component_2"

        # Generate from component1
        numbers1_before = [
            random_manager.uniform(component=component1) for _ in range(5)
        ]

        # Generate from component2 (should not affect component1)
        [random_manager.uniform(component=component2) for _ in range(10)]

        # Generate more from component1
        numbers1_after = [
            random_manager.uniform(component=component1) for _ in range(5)
        ]

        # Reset and generate just from component1
        random_manager.reset_all_rng()
        expected_numbers = [
            random_manager.uniform(component=component1) for _ in range(10)
        ]

        # The component1 sequence should be unaffected by component2 usage
        np.testing.assert_array_equal(
            numbers1_before + numbers1_after, expected_numbers
        )

    def test_seed_zero_generates_random_seed(self) -> None:
        """Test that setting seed to zero generates a random seed."""
        random_manager = RandomManager()
        object.__setattr__(Configuration().random_manager, "SEED", 0)
        random_manager.reset_all_rng()

        # Should not be zero
        main_seed1 = random_manager._main_seed
        assert main_seed1 != 0

        # Resetting the seed should give a different random seed
        random_manager.reset_all_rng()
        main_seed2 = random_manager._main_seed
        assert main_seed2 != 0
        assert main_seed1 != main_seed2

    def test_uniform_distribution_properties(self) -> None:
        """Test that the uniform method returns values with correct properties."""
        random_manager = RandomManager()
        object.__setattr__(Configuration().random_manager, "SEED", 42)
        random_manager.reset_all_rng()

        # Generate sample of random numbers
        sample_size = 1000
        numbers = [random_manager.uniform() for _ in range(sample_size)]

        # All numbers should be between 0 and 1
        assert all(0 <= x <= 1 for x in numbers), (
            "All uniform values should be between 0 and 1"
        )

        # Check distribution properties
        mean = np.mean(numbers)
        assert 0.4 < mean < 0.6, "Mean of uniform distribution should be close to 0.5"

    def test_uniform_reproducibility_with_seed(self) -> None:
        """Test that uniform method produces reproducible results with same seed."""
        random_manager = RandomManager()
        object.__setattr__(Configuration().random_manager, "SEED", 42)
        random_manager.reset_all_rng()

        # Generate first sequence
        numbers1 = [random_manager.uniform() for _ in range(100)]

        # Reset with same seed and generate again
        random_manager.reset_all_rng()
        numbers2 = [random_manager.uniform() for _ in range(100)]

        assert np.allclose(numbers1, numbers2), (
            "The same seed should produce the same sequence of random numbers"
        )

    def test_uniform_different_seeds_different_sequences(self) -> None:
        """Test that different seeds produce different random sequences."""
        random_manager = RandomManager()

        # Generate sequence with seed 42
        object.__setattr__(Configuration().random_manager, "SEED", 42)
        random_manager.reset_all_rng()
        numbers1 = [random_manager.uniform() for _ in range(100)]

        # Generate sequence with seed 43
        object.__setattr__(Configuration().random_manager, "SEED", 43)
        random_manager.reset_all_rng()
        numbers2 = [random_manager.uniform() for _ in range(100)]

        assert not np.allclose(numbers1, numbers2), (
            "Different seeds should produce different sequences of random numbers"
        )

    def test_component_seed_zero_generates_random_sequences(self) -> None:
        """Test that component seed zero generates different results on each reset."""
        random_manager = RandomManager()
        object.__setattr__(Configuration().random_manager, "SEED", 0)
        random_manager.reset_all_rng()

        component = "test_component"
        Configuration().random_manager.COMPONENT_SEEDS[component] = 0
        random_manager.reset_fixed_seed_components()

        # Store first sequence of random numbers
        sequence1 = [random_manager.uniform(component=component) for _ in range(5)]

        # Reset and generate new sequence
        random_manager.reset_fixed_seed_components()
        sequence2 = [random_manager.uniform(component=component) for _ in range(5)]

        # The sequences should be different since seed is randomly generated each time
        with pytest.raises(AssertionError):
            np.testing.assert_array_equal(sequence1, sequence2)

    @pytest.mark.parametrize(
        "component_name", ["vehicles", "users", "environment", "simulation_engine"]
    )
    def test_component_rng_isolation(self, component_name: str) -> None:
        """Test that each component gets its own isolated RNG.

        Parameters
        ----------
        component_name : str
            Name of the component to test RNG isolation for.
        """
        random_manager = RandomManager()
        object.__setattr__(Configuration().random_manager, "SEED", 42)
        random_manager.reset_all_rng()

        # Get RNG for this component
        component_rng = random_manager.get_rng(component_name)

        # Verify it's different from main RNG
        main_rng = random_manager.get_rng()
        assert component_rng is not main_rng, (
            "Component RNG should be different from main RNG"
        )

        # Verify consistent access
        assert random_manager.get_rng(component_name) is component_rng, (
            "Multiple calls should return same component RNG instance"
        )

    def test_reset_all_rng_resets_component_rngs(self) -> None:
        """Test that reset_all_rng properly resets component RNGs to initial state."""
        random_manager = RandomManager()
        object.__setattr__(Configuration().random_manager, "SEED", 42)
        random_manager.reset_all_rng()

        component = "test_component"

        # Get component RNG and generate some numbers
        component_rng = random_manager.get_rng(component)
        initial_numbers = [
            random_manager.uniform(component=component) for _ in range(5)
        ]

        # Generate more numbers to advance the RNG state
        [random_manager.uniform(component=component) for _ in range(10)]

        # Verify the RNG still exists
        assert component in random_manager._component_rngs
        assert random_manager._component_rngs[component] is component_rng

        # Reset all RNGs
        random_manager.reset_all_rng()

        # After reset, component RNGs are cleared, so we need to get a new one
        # But it should produce the same initial sequence due to deterministic seeding
        reset_numbers = [random_manager.uniform(component=component) for _ in range(5)]

        # Should get the same sequence as initially generated
        np.testing.assert_array_equal(initial_numbers, reset_numbers)
