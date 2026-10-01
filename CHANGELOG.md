# Changelog

## [0.3.0](https://github.com/IS3UniCologne/urban-mobility-simulation/compare/v0.2.0...v0.3.0) (2026-09-18)


### ⚠ BREAKING CHANGES

* **accounting:** operator.cost_ledger and the cost_accounting import path are gone.
* **operator:** revenue is now gross, costs and profit are tracked separately. Cost configuration has been moved into separate Config subclasses. Charging cost is now based on kWh actually charged rather than requested.

### Features

* **cost_accounting:** book revenue in the CostLedger, so revenue and cost come from one object. ([1181d34](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/1181d34cda6e7a2e00111fcb38e1c1d9daf632e1))
* **operator:** centralized cost accounting in Operator CostLedger ([e4a0519](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/e4a0519640e8e02e03f732e087d83a500b3adb7e))


### Refactors

* **accounting:** rename CostLedger to Ledger, rename the reporter contracts to VehicleLedger and WorkerLedger. ([7fd33c6](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/7fd33c62f573a808d28b68fa8cff524621100401))
* **cost_accounting:** remove null cost reporters and make assignment required ([984a6ae](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/984a6ae58726ae7acfd6ec4060e5cba6fdbef046))
* **cost_accounting:** remove ONLINE/OFFLINE split for daily vehicle costs ([cd24b76](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/cd24b76cbd237c723d3d0e1c794d2e94f05bbee3))
* fix type hints and docstrings on various connected modules. Minor refactoring where necessary for clean typing. ([04e85f0](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/04e85f031ff886bfeb26b8ccbebf505a0bb22c88))
* fix type hints and docstrings on various connected modules… ([7d3e8cd](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/7d3e8cd11f6095f0aec4b85dd40fb63dcbb00c24))

## [0.2.0](https://github.com/IS3UniCologne/urban-mobility-simulation/compare/v0.1.0...v0.2.0) (2026-07-14)


### ⚠ BREAKING CHANGES

* **cleanup:** The old tracking module has been removed. This breaks some parts of the learning module too.
* **vehicle_choice_model:** The old vehicle choice model interface has been removed.

### Features

* **cli:** add --viz toggle to run the live visualization ([e53a07e](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/e53a07e55a47dff26130e3ea30bae804dde0e520))
* **cli:** add log level override to umosim run ([0a8e425](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/0a8e4258dff5c7696480d599da24f1b8a9c3ca69))
* **cli:** umosim CLI for input data scaffolding, synthetic demand generation and various utility stuff ([d32a092](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/d32a0929847298b9e4510e99249ff75116092643))
* **environment:** infer bounding box and hex layers at runtime. Check if demand and supply fall within hex layer. ([f159c1d](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/f159c1d85cbd54a662431129503359882fff7070))
* **infrastructure:** auto-derive distance matrix ([6536c8c](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/6536c8c8903c1bf3919a6080c165a56547c4cb5a))
* **supply:** dedicated supply loading module ([dde56a2](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/dde56a2b68589e84b5260c4ec4dca5ff4aec66dc))
* **supply:** optional dataset and fleet-level supply.parquet with demand-derived fallback. ([9a2cf13](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/9a2cf13cc902f5b14c7cbf4edb9d3c7af7a45673))


### Bug Fixes

* **config:** get station power and vehicle relocation velocity from correct operations object instead of picking first in config ([30aa2ba](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/30aa2bae015229bb3b1a238e29eb624b4625468e))
* **configuration:** update demand modifier handling to accept multiple files (this was the initial behaviour) ([d08fcbe](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/d08fcbe7cec4dc3ba7ecb337fecb1040e6c45e48))
* **tests:** fix stale e2e tests after branch switch ([28eb5c7](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/28eb5c7db85a08bf763d8d7a042935d694da98e2))
* **vehicle_session:** Check if simulation is still running before releasing reservations during vehicle sessions. ([60722b4](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/60722b491bac1a8c3f59fe6a1deb8a8da5a252b4))
* **visualization:** per-session state and lazy panel rendering. ([794da41](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/794da41adc66179040757920ed42cf4a3515c29a))


### Refactors

* **enums:** Drop deprecated column name properties. They are now stored in the demand schema. ([ad8af47](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/ad8af4758375e83a7bc26ec85e797906678982b3))
* **environment:** extract bbox + hex layer derivation into dedicated modules. ([5e470ec](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/5e470ecb25dfcdf32d666b495fd51de27b5bc075))
* **timetable:** switch from CSV to Parquet for timetable import ([e420c26](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/e420c26a2447e5275fc910c0fc466d03a6a91dd8))
* **vehicle_choice_model:** remove deprecated vehicle choice models and related code. New models are in simulation.agent.user.choice_model. ([44da0ef](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/44da0efe32b030c2950bb96764a03af9b38ae14f))


### Documentation

* Add CONTRIBUTING.md, update README.md ([c8f4b8e](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/c8f4b8e1088a3146a7f430f9a77bb371e29a9006))
* Add CONTRIBUTING.md, update README.md ([82d6a47](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/82d6a47488ace2b2ffd207bd2300bcf765f9fe04))


### Miscellaneous

* **cleanup:** Remove the now deprecated tracking module. ([0bfc8b6](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/0bfc8b6f9f77fa0def6fada07bca8f9faed63c98))
