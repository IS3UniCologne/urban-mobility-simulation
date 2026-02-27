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
    STANDBY = VehicleState(name="STANDBY")
    TRANSPORTING = VehicleState(name="TRANSPORTING")
    SERVICING = VehicleState(name="SERVICING")
    OFFLINE = VehicleState(name="OFFLINE")

    # Transporting
    PICK_UP = VehicleState(name="PICK_UP", parent=TRANSPORTING)
    DRIVING = VehicleState(name="DRIVING", parent=TRANSPORTING)
    WAITING_FOR_USER = VehicleState(name="WAITING_FOR_USER", parent=TRANSPORTING)
    AT_STOP = VehicleState(name="AT_STOP", parent=TRANSPORTING)
    EN_ROUTE = VehicleState(name="EN_ROUTE", parent=TRANSPORTING)
    AT_TERMINAL = VehicleState(name="AT_TERMINAL", parent=TRANSPORTING)

    # Servicing
    RELOCATING = VehicleState(name="RELOCATING", parent=SERVICING)
    CHARGING = VehicleState(name="CHARGING", parent=SERVICING)
    WAITING_FOR_CHARGING = VehicleState(name="WAITING_FOR_CHARGING", parent=SERVICING)

    # Allowed transitions
    TRANSITIONS: ClassVar[dict[VehicleState, set[VehicleState]]] = {
        # TODO: Check if these transitions make sense
        # Ride-hailing/shared mobility
        STANDBY: {PICK_UP, DRIVING, RELOCATING, CHARGING, OFFLINE, WAITING_FOR_USER},
        PICK_UP: {DRIVING, STANDBY},
        DRIVING: {STANDBY, CHARGING, RELOCATING},
        WAITING_FOR_USER: {DRIVING, STANDBY},
        # Public transport
        AT_STOP: {EN_ROUTE, AT_TERMINAL, STANDBY},
        EN_ROUTE: {AT_STOP, AT_TERMINAL, STANDBY},
        AT_TERMINAL: {EN_ROUTE, STANDBY},
        # Operator tasks
        RELOCATING: {STANDBY, WAITING_FOR_CHARGING, CHARGING},
        CHARGING: {STANDBY, RELOCATING},
        WAITING_FOR_CHARGING: {CHARGING, STANDBY},
        # Offline
        OFFLINE: {STANDBY},
    }
