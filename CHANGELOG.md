# Changelog

## [1.3.7.1] - 2026-05-20

### Added

- Support not just one address but a list of addresses for contracts linked with the conditional configuration by `coinpair`.
- Improve the default configuration for conditional publishing by making it network-dependent (`chainId`). similar to `GAS_LIMIT_ADDR`.
- Implement `supervisord` within Docker for process management (it's cleaner).
- Add some script to build the docker image.
- Add support for MOC V3 in conditional parameter thresholds.
- Add support for MocMultiCollateralGuard in conditional parameter thresholds.
- Add Per-Pair Fallback Overrides.
- Use `DWAP` coinpair option for `RIF/USD`.  
- Update the `moneyonchain-prices-source` dependency to the latest "no beta" version.

### Fixed

- Fixing Fallback Oracle Priority Issue After **UNNEED→NEED** state cycles.
- Fixing circular import issue.

### Changed

- No gas limit address for testnet as default.

### Removed

- Remove default params for testnet MOC V3 in conditional parameter thresholds.

____
