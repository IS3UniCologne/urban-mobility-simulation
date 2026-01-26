"""Vehicle state definitions and transitions."""

from __future__ import annotations

from typing import ClassVar

from simulation.helper.state_machine import State


class VehicleState(State):
    """Vehicle-Specific State for Hierarchical State Machine."""

    pass


class VehicleStates:
    """Namespace for vehicle state constants and transitions."""

    # Root level states
    IDLE = VehicleState(name="IDLE")
    IN_USE = VehicleState(name="IN_USE")
    OFFLINE = VehicleState(name="OFFLINE")

    # In-use subcategories
    SERVING_PASSENGERS = VehicleState(name="SERVING_PASSENGERS", parent=IN_USE)
    OPERATOR_TASK = VehicleState(name="OPERATOR_TASK", parent=IN_USE)

    # Passenger operations - Ride-hailing/shared mobility
    PICK_UP = VehicleState(name="PICK_UP", parent=SERVING_PASSENGERS)
    TRANSPORTING = VehicleState(name="TRANSPORTING", parent=SERVING_PASSENGERS)

    # Passenger operations - Public transport
    AT_STOP = VehicleState(name="AT_STOP", parent=SERVING_PASSENGERS)
    EN_ROUTE = VehicleState(name="EN_ROUTE", parent=SERVING_PASSENGERS)
    AT_TERMINAL = VehicleState(name="AT_TERMINAL", parent=SERVING_PASSENGERS)

    # Operator task states
    RELOCATING = VehicleState(name="RELOCATING", parent=OPERATOR_TASK)
    CHARGING = VehicleState(name="CHARGING", parent=OPERATOR_TASK)
    PRE_SERVICE = VehicleState(name="WAITING_FOR_CHARGING", parent=OPERATOR_TASK)

    # Allowed transitions
    TRANSITIONS: ClassVar[dict[VehicleState, set[VehicleState]]] = {
        # TODO: Check if these transitions make sense
        # Ride-hailing/shared mobility
        IDLE: {PICK_UP, TRANSPORTING, RELOCATING, CHARGING, OFFLINE},
        PICK_UP: {TRANSPORTING, IDLE},
        TRANSPORTING: {IDLE, CHARGING, RELOCATING},
        # Public transport
        AT_STOP: {EN_ROUTE, AT_TERMINAL, IDLE},
        EN_ROUTE: {AT_STOP, AT_TERMINAL, IDLE},
        AT_TERMINAL: {EN_ROUTE, IDLE},
        # Operator tasks
        RELOCATING: {IDLE, CHARGING},
        CHARGING: {IDLE, RELOCATING},
        # Offline
        OFFLINE: {IDLE},
    }
