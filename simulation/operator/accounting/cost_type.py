"""Cost type enumeration for operator cost accounting."""

from enum import Enum


class CostType(Enum):
    """Categories of costs attributed to an operator."""

    VEHICLE_DISTANCE = "vehicle_distance"
    VEHICLE_RELOCATION_DISTANCE = "vehicle_relocation_distance"
    VEHICLE_CHARGING = "vehicle_charging"
    VEHICLE_HOLDING = "vehicle_holding"
    DRIVER_PAYMENT = "driver_payment"
    WORKER_LABOR = "worker_labor"
