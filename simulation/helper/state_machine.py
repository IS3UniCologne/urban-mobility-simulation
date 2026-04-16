"""Pseudo-hierarchical state machine.

States can have parent-child relationships to form hierarchies for state organization.

State transitions are NOT hierarchical, i.e., transitions must be explicitly defined
between individual states regardless of their hierarchical relationship.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Self, TypeVar

from simulation.helper.exceptions import InvalidStateTransitionError


@dataclass(frozen=True, slots=True)
class State:
    """
    Hierarchical state representation for use in state machines.

    Parameters
    ----------
    name : str
        State name
    parent : Self or None
        Parent state in hierarchy, or None for root states

    Attributes
    ----------
    name : str
        State name
    parent : Self or None
        Parent state reference
    """

    name: str
    parent: Self | None = None

    def is_descendant_of(self, other: Self) -> bool:
        """
        Check if this state is a descendant of another state.

        Parameters
        ----------
        other : Self
            Potential ancestor state

        Returns
        -------
        bool
            True if this state is a descendant of other
        """
        current = self.parent
        while current is not None:
            if current is other:
                return True
            current = current.parent
        return False

    def is_ancestor_of(self, other: Self) -> bool:
        """
        Check if this state is an ancestor of another state.

        Parameters
        ----------
        other : Self
            Potential descendant state

        Returns
        -------
        bool
            True if this state is an ancestor of other
        """
        return other.is_descendant_of(self)

    def get_ancestors(self) -> list[Self]:
        """
        Get all ancestor states from parent to root.

        Returns
        -------
        list of Self
            List of ancestor states, ordered from immediate parent to root
        """
        ancestors = []
        current = self.parent
        while current is not None:
            ancestors.append(current)
            current = current.parent
        return ancestors

    def get_root(self) -> Self:
        """
        Get the root state of this hierarchy.

        Returns
        -------
        Self
            Root state (the state with no parent)
        """
        current = self
        while current.parent is not None:
            current = current.parent
        return current

    def get_path(self) -> str:
        """
        Get full hierarchical path from root to this state.

        Returns
        -------
        str
            Path string like "IN_USE/USER_TRIP/PICK_UP"
        """
        path = [self.name]
        current = self.parent
        while current is not None:
            path.insert(0, current.name)
            current = current.parent
        return "/".join(path)

    def __str__(self) -> str:
        """Return string representation of the state.

        Returns
        -------
        str
            String representation of the state and its path.
        """
        return self.get_path()


StateT = TypeVar("StateT", bound="State")


class StateMachine(Generic[StateT]):
    """
    Generic state machine with hierarchical states and non-hierarchical transitions.

    Parameters
    ----------
    initial_state : StateT
        Initial state
    allowed_transitions : dict of StateT to set of StateT
        Valid state transitions

    Attributes
    ----------
    current_state : StateT
        Current state of the machine
    """

    def __init__(
        self, initial_state: StateT, allowed_transitions: dict[StateT, set[StateT]]
    ) -> None:
        self._current_state = initial_state
        self._allowed_transitions = allowed_transitions
        self._history: list[StateT] = [initial_state]

    @property
    def current_state(self) -> StateT:
        """Get current state."""
        return self._current_state

    @property
    def history(self) -> list[StateT]:
        """Get state transition history."""
        return self._history.copy()

    def can_transition_to(self, target_state: StateT) -> bool:
        """
        Check if transition to target state is allowed.

        Parameters
        ----------
        target_state : StateT
            Target state

        Returns
        -------
        bool
            True if transition is valid
        """
        allowed = self._allowed_transitions.get(self._current_state, set())
        return target_state in allowed

    def transition_to(self, target_state: StateT) -> None:
        """
        Transition to new state.

        Parameters
        ----------
        target_state : StateT
            Target state to transition to

        Raises
        ------
        InvalidStateTransitionError
            If transition is not allowed
        """
        if not self.can_transition_to(target_state):
            msg = (
                f"Invalid state transition: {self._current_state.get_path()} "
                f"-> {target_state.get_path()}. \n State history (last 5): {', '.join(state.name for state in self._history[-5:])}   "
            )
            raise InvalidStateTransitionError(msg)

        self._current_state = target_state
        self._history.append(target_state)

    def is_in_state_or_descendant(self, category: StateT) -> bool:
        """
        Check if current state is in category (exact match or descendant).

        Parameters
        ----------
        category : StateT
            Category state to check

        Returns
        -------
        bool
            True if current state is category or child of category
        """
        return self._current_state is category or self._current_state.is_descendant_of(
            category
        )

    def get_state_path(self) -> str:
        """
        Get full hierarchical path of current state.

        Returns
        -------
        str
            Path from root to current state
        """
        return self._current_state.get_path()
