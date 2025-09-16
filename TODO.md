# Release 1.3.7.1

## To do

*2025-04-11*

- [x] Support not just one address but a list of addresses for contracts linked with the conditional configuration by `coinpair`.
- [x] Improve the default configuration for conditional publishing by making it network-dependent (`chainId`). similar to `GAS_LIMIT_ADDR`.
- [x] Implement `supervisord` within Docker for process management (it's cleaner).
- [x] Add some script to build the docker image.
- [x] Add support for MOC V3 in conditional parameter thresholds.
- [x] Remove default params for testnet MOC V3 in conditional parameter thresholds.
- [x] No gas limit address for testnet as default.
- [x] Add support for MocMultiCollateralGuard in conditional parameter thresholds.
- [x] Fixing Fallback Oracle Priority Issue After **UNNEED→NEED** state cycles.
- [x] Add Per-Pair Fallback Overrides.
- [x] Fixing circular import issue.
- [ ] Update the `moneyonchain-prices-source` dependency to the latest "no beta" version (_It will probably be necessary a new release of this dependency first_).

____
