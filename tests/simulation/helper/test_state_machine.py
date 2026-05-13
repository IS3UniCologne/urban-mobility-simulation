"""Unit tests for StateMachine."""

import pytest

from simulation.helper.exceptions import InvalidStateTransitionError
from simulation.helper.state_machine import State, StateMachine

# Minimal states for transition tests: cycle A→B→C→A
_A = State("A")
_B = State("B")
_C = State("C")
_TRANSITIONS: dict[State, set[State]] = {_A: {_B}, _B: {_C}, _C: {_A}}

# Minimal hierarchy for hierarchy tests
_CAT_X = State("CAT_X")
_CAT_Y = State("CAT_Y")
_CHILD_X1 = State("CHILD_X1", parent=_CAT_X)
_CHILD_X2 = State("CHILD_X2", parent=_CAT_X)
_CHILD_Y1 = State("CHILD_Y1", parent=_CAT_Y)
_HIERARCHY_TRANSITIONS: dict[State, set[State]] = {
    _CAT_X: {_CHILD_X1, _CHILD_X2},
    _CAT_Y: {_CHILD_Y1},
    _CHILD_X1: {_CHILD_X2, _CAT_X},
    _CHILD_X2: {_CHILD_X1, _CAT_X},
    _CHILD_Y1: {_CAT_Y},
}


@pytest.mark.unit
class TestStateMachine:
    """Unit tests for the generic StateMachine class."""

    @pytest.fixture
    def sm(self) -> StateMachine[State]:
        """State machine with cycle A→B→C→A, starting at A."""
        return StateMachine(_A, allowed_transitions=_TRANSITIONS)

    def test_initial_state_is_set(self, sm: StateMachine[State]) -> None:
        """Initial state matches the constructor argument."""
        assert sm.current_state is _A

    def test_valid_transition_updates_state(self, sm: StateMachine[State]) -> None:
        """Transitioning to an allowed state updates current_state."""
        sm.transition_to(_B)
        assert sm.current_state is _B

    def test_invalid_transition_raises(self, sm: StateMachine[State]) -> None:
        """Transitioning to a disallowed state raises InvalidStateTransitionError."""
        with pytest.raises(InvalidStateTransitionError):
            sm.transition_to(_C)  # A→C not in table

    def test_error_message_contains_states(self, sm: StateMachine[State]) -> None:
        """Error message includes the source and target state names."""
        with pytest.raises(InvalidStateTransitionError, match="A"):
            sm.transition_to(_C)

    def test_can_transition_to_allowed(self, sm: StateMachine[State]) -> None:
        """can_transition_to returns True for a valid target."""
        assert sm.can_transition_to(_B) is True

    def test_can_transition_to_disallowed(self, sm: StateMachine[State]) -> None:
        """can_transition_to returns False for a disallowed target."""
        assert sm.can_transition_to(_C) is False

    def test_is_in_state_exact_match(self, sm: StateMachine[State]) -> None:
        """is_in_state_or_descendant returns True when current state matches exactly."""
        assert sm.is_in_state_or_descendant(_A) is True

    def test_is_in_state_descendant_match(self) -> None:
        """is_in_state_or_descendant returns True when current state is a descendant."""
        sm: StateMachine[State] = StateMachine(
            _CHILD_X1, allowed_transitions=_HIERARCHY_TRANSITIONS
        )
        assert sm.is_in_state_or_descendant(_CAT_X) is True

    def test_is_in_state_second_child_of_same_category(self) -> None:
        """is_in_state_or_descendant returns True for a sibling child of the same category."""
        sm: StateMachine[State] = StateMachine(
            _CHILD_X2, allowed_transitions=_HIERARCHY_TRANSITIONS
        )
        assert sm.is_in_state_or_descendant(_CAT_X) is True

    def test_is_in_state_child_of_other_category(self) -> None:
        """is_in_state_or_descendant returns False when child belongs to a different category."""
        sm: StateMachine[State] = StateMachine(
            _CHILD_Y1, allowed_transitions=_HIERARCHY_TRANSITIONS
        )
        assert sm.is_in_state_or_descendant(_CAT_X) is False

    def test_is_in_state_no_match(self, sm: StateMachine[State]) -> None:
        """is_in_state_or_descendant returns False when state doesn't match."""
        assert sm.is_in_state_or_descendant(_B) is False
