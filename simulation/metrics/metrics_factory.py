from .modules.general_metrics import GeneralMetrics
from .modules.service_provider_metrics import ServiceProviderMetrics
from .modules.customer_metrics import CustomerMetrics
from .modules.society_metrics import SocietyMetrics


class MetricsFactory:
    def __init__(self, transactions):
        self._general_metrics = GeneralMetrics(transactions)
        self._service_provider = ServiceProviderMetrics(transactions)
        self._customer_metrics = CustomerMetrics(transactions)
        self._society_metrics = SocietyMetrics(transactions)
        self._transactions = transactions

    @property
    def general_metrics(self) -> GeneralMetrics:
        return self._general_metrics

    @property
    def service_provider_metrics(self) -> ServiceProviderMetrics:
        return self._service_provider

    @property
    def customer_metrics(self) -> CustomerMetrics:
        return self._customer_metrics

    @property
    def society_metrics(self) -> SocietyMetrics:
        return self._society_metrics

    def print_simulation_summary(
        self,
        number_of_vehicles: dict,
        cost_per_vehicle_km: dict,
        co2_per_km_per_vehicle: dict,
    ):
        print("############ Simulation Summary ############")
        print(" ")
        self._general_metrics.print_summary()
        self._service_provider.print_summary(number_of_vehicles, cost_per_vehicle_km)
        self._customer_metrics.print_summary()
        self._society_metrics.print_summary(co2_per_km_per_vehicle)
        print(" ")
        print("#" * 40)
