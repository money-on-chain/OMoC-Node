# Changelog

## [1.3.7.3] - 2026-09-10

### Fixed

- Align signature validation with the smart contract: require 65-byte signatures and accept only recovery byte (`v`) values of `0`, `1`, `27`, or `28`. Invalid signatures now return `False` during verification.

### Changed

- Disable RIFUSD conditional publishing configuration by default on mainnet and testnet by commenting out the endpoint defaults. `ORACLE_OFFLINE_CFG_RIFUSD` now defaults to `false` unless explicitly configured.
- Update the Docker image's `moneyonchain-prices-source` dependency from `0.7.7` to `0.7.8`.
- Move the Docker rebuild script to `Docker/scripts/` and update its download URL in `Docker/update.sh`.
- Replace the legacy disk cleanup script with a Docker-oriented version in `Docker/scripts/`, including Docker log cleanup and updated usage documentation.

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
