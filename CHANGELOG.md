# Changelog

## [0.5.0](https://github.com/IS3UniCologne/urban-mobility-simulation/compare/v0.4.0...v0.5.0) (2026-11-13)


### Features

* allow time-dependent prices for charging ([#378](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/378)) ([1d0e151](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/1d0e1514c47e9eddcb2854634a8b48e48277a220))


### Refactors

* replace deprecated pandas inplace parameter with assignments ([#409](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/409)) ([9d8ce9f](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/9d8ce9f96d2473ef20108929a134d4de432e21fb)), closes [#405](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/405)


### Dependencies

* bump soupsieve from 2.10 to 4.0 ([#412](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/412)) ([1e93096](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/1e9309686f64b140f1b881392680c667c7344a2b))

## [0.4.0](https://github.com/IS3UniCologne/urban-mobility-simulation/compare/v0.3.0...v0.4.0) (2026-11-09)


### ⚠ BREAKING CHANGES

* **cleanup:** learning/ and the DQN and Sarsa agents in simulation/agent/ are gone. Configuration loses dynamic_routing, dynamic_checkpoint_routing and dqn. Bus loses use_learning_agent.
* **search_engine:** AV_PRICE_REDUCTION, MAX_PICKUP_DISTANCE, PRICE_ENTERING, PRICE_PER_MINUTE, PRICE_PER_KM and MINIMUM_PRICE move from RideHailingOperationsConfig to RideHailingSearchEngineConfig. RideHailingFleet.get_available_vehicles_to_user is removed.

### Features

* configurable shift check interval ([#370](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/370)) ([9c538ae](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/9c538ae2a8bf5ad2b3e3c1bd337a1843485d27f4))
* **rl:** reinforcement learning harness using Gymnasium ([#365](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/365)) ([143f64e](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/143f64e94cae6a7426b45fc03f896e218a3335e8))
* **simulation:** accept a main seed on Simulation, so a caller can seed ([143f64e](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/143f64e94cae6a7426b45fc03f896e218a3335e8))


### Performance

* various performance improvments ([#371](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/371)) ([1857a8b](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/1857a8bab7c614e36d99e86219fec841349a7989))


### Refactors

* **cleanup:** remove the learning package and the old RL agents ([#396](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/396)) ([7313ac1](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/7313ac1f58fab09402940cb2d6c1f99f0f5e8730))
* **search_engine:** move ride-hailing prices and pickup radius to the search engine config ([#366](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/366)) ([379ae51](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/379ae51f0043386c4687706016fb5f3305015b93))


### Documentation

* add readthedocs configuration file ([b147402](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/b147402c256a040d376955a9a92a24b6f107fde9))
* add Sphinx documentation ([#369](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/369)) ([f412255](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/f412255dd04324d96c89c120e4766471c8962091))


### Dependencies

* bump certifi from 2026.4.22 to 2026.10.18 ([#390](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/390)) ([438bda9](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/438bda9f6487889d6f7d7cf041a4e24bb5c9f6ef))
* bump fsspec from 2026.4.0 to 2026.6.0 ([#381](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/381)) ([4bd9f11](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/4bd9f11a95ae505e0bb35a5791532d908fa78400))
* bump pandas from 3.0.5 to 3.0.6 in the runtime-dependencies group across 1 directory ([#362](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/362)) ([1e7d193](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/1e7d193807b11f299c54eee37e72a22a66ddd20e))
* bump pillow from 12.3.0 to 13.0.0 ([#387](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/387)) ([547d33c](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/547d33cfbe7a40c5f31d8475e015778cddccb8c8))
* bump pyarrow from 25.0.1 to 26.0.0 ([#385](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/385)) ([f51efdd](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/f51efdde5d06100d0450ff8e1ff076c127bb853c))
* bump the runtime-dependencies group across 1 directory with 3 updates ([#393](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/393)) ([b7a95ad](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/b7a95adb8b41be23687c03fb729393efa5d0da63))
* bump the runtime-dependencies group with 2 updates ([#380](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/380)) ([12baecd](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/12baecd83a196298c8d3a8016c9b37c542a4e3e2))
* bump the runtime-dependencies group with 3 updates ([#384](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/384)) ([04679d7](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/04679d79e58df4459a61a72b1a04093cfb3b78fb))
* bump tornado from 6.5.7 to 6.5.9 ([#374](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/374)) ([ea06bec](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/ea06becb643bc59d24b46cd2cf39227f0629075e))
* bump virtualenv from 21.3.3 to 21.7.13 ([#373](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/373)) ([7ea1be7](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/7ea1be7fa78d70f4e0e5a23e4e850d235da45e96))
* bump virtualenv from 21.7.13 to 21.14.13 ([#391](https://github.com/IS3UniCologne/urban-mobility-simulation/issues/391)) ([17f60ad](https://github.com/IS3UniCologne/urban-mobility-simulation/commit/17f60ada65cde3eff45d34031a4f656baaeed883))

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
