"""Interactive prompt helpers for the umosim CLI."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


def is_interactive() -> bool:
    """Return True if stdin is a TTY (i.e. a human is at the keyboard)."""
    return sys.stdin.isatty()


def ensure_required_arg(
    value: T | None, *, missing_message: str, prompt: Callable[[], T]
) -> T:
    """Resolve a required CLI argument: pass-through, prompt, or fail.

    Returns *value* if set, prompts interactively when at a TTY, and otherwise
    raises ``SystemExit`` with *missing_message*.
    """
    if value is not None:
        return value
    if is_interactive():
        return prompt()
    raise SystemExit(missing_message)


def prompt_text(label: str, default: str | None = None) -> str:
    """Prompt for a non-empty string, re-prompting on empty input."""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        print("  Value is required.")


def prompt_int(label: str, default: int) -> int:
    """Prompt for an integer, falling back to *default* on empty input."""
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            print("  Enter a whole number.")


def prompt_float(label: str, default: float) -> float:
    """Prompt for a float, falling back to *default* on empty input."""
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            print("  Enter a number.")


def prompt_yes_no(label: str, default: bool = False) -> bool:
    """Prompt for a yes/no answer, returning *default* on empty input."""
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"{label} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def prompt_choice(label: str, choices: list[str]) -> str:
    """Print a numbered menu and return the selected item."""
    print(f"\n{label}")
    for i, choice in enumerate(choices, 1):
        print(f"  {i}. {choice}")
    while True:
        raw = input(f"Enter 1-{len(choices)}: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        print(f"  Enter a number between 1 and {len(choices)}.")


def prompt_multi_choice(
    label: str, choices: list[str], defaults: list[str] | None = None
) -> list[str]:
    """Print a numbered menu and return a list of selected items.

    Accepts comma-separated numbers; repeating a number selects that choice
    more than once. Empty input returns *defaults*.
    """
    effective_defaults = defaults or choices
    default_str = ", ".join(effective_defaults)
    print(f"\n{label}")
    for i, choice in enumerate(choices, 1):
        print(f"  {i}. {choice}")
    print(
        "  Type comma-separated numbers; repeat a number to add that type "
        "twice (e.g. 1,1,2). Press Enter to accept the default."
    )
    while True:
        raw = input(f"Selection [{default_str}]: ").strip()
        if not raw:
            return list(effective_defaults)
        parts = [p.strip() for p in raw.split(",")]
        if all(p.isdigit() and 1 <= int(p) <= len(choices) for p in parts):
            return [choices[int(p) - 1] for p in parts]
        print(f"  Enter comma-separated numbers between 1 and {len(choices)}.")
