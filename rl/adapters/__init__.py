"""Seam adapters are the connector between the simulation and an RL problem.

To create a new adapter, subclass an existing simulation component.
Call the DecisionBroker's ``decide`` method where the simulation component needs a decision.
"""

from rl.adapters.admission import BrokeredAdmissionSearchEngine, Search

__all__ = ["BrokeredAdmissionSearchEngine", "Search"]
