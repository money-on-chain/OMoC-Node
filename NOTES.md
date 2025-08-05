# Notes related to the branch purpose

## Add Per-Pair Fallback Overrides

* Introduce per-pair fallback overrides by checking for `ORACLE_ENTERING_FALLBACKS_AMOUNTS_<PAIR>` environment variables, falling back to the global value when no override is present.

* Update Oracle turn logic to use these pair-specific configurations when evaluating publishing eligibility.

* Document the new override mechanism and provided an example configuration for setting pair-specific fallback sequences.
