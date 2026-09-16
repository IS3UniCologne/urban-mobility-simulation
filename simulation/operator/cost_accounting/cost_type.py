"""Cost type enumeration for operator cost accounting."""

from enum import Enum


class CostType(Enum):
    """Categories of operating cost drivers attributed to an operator."""

    VEHICLE_DISTANCE = "vehicle_distance"
    VEHICLE_RELOCATION_DISTANCE = "vehicle_relocation_distance"
    VEHICLE_CHARGING = "vehicle_charging"
    VEHICLE_TIME = "vehicle_time"
    DRIVER_PAYMENT = "driver_payment"
    WORKER_TIME = "worker_time"
