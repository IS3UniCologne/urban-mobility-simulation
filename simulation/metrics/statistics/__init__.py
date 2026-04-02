"""
Intermediary statistics classes used for metrics calculation.

These classes are responsible for calculating and storing (incremental) statistics.
They are used by metrics providers to get the final metrics data.

Implementation should focus on efficient incremental updates to avoid slowdowns in
long simulations. This means we avoid full scans or recomputations where possible.
"""
