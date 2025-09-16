# Notes related to the branch purpose

## Fixing circular import issue


### Problem description

Error traceback:

```
Traceback (most recent call last):
  File "/usr/lib/python3.8/runpy.py", line 194, in _run_module_as_main
    return _run_code(code, main_globals, None,
  File "/usr/lib/python3.8/runpy.py", line 87, in _run_code
    exec(code, run_globals)
  File "/OMoC-Node/servers/oracle/src/main.py", line 10, in <module>
    from oracle.src.main_loop import MainLoop
  File "/OMoC-Node/servers/oracle/src/main_loop.py", line 7, in <module>
    from common.services.contract_factory_service import ContractFactoryService
  File "/OMoC-Node/servers/common/services/contract_factory_service.py", line 10, in <module>
    from common.services.coin_pair_price_service import CoinPairService, TasksRunnerService
  File "/OMoC-Node/servers/common/services/coin_pair_price_service.py", line 12, in <module>
    from oracle.src.oracle_coin_pair_service import OracleCoinPairService
  File "/OMoC-Node/servers/oracle/src/oracle_coin_pair_service.py", line 7, in <module>
    from common.services.coin_pair_price_service import CoinPairService, TasksRunnerService
ImportError: cannot import name 'CoinPairService' from partially initialized module 'common.services.coin_pair_price_service' (most likely due to a circular import) (/OMoC-Node/servers/common/services/coin_pair_price_service.py)
```

The traceback shows a circular import: `coin_pair_price_service` imports `OracleCoinPairService`, while `oracle_coin_pair_service` imports `CoinPairService` and `TasksRunnerService`. When Python loads one module, it tries to import the other before finishing initialization, so the symbol isn’t defined yet and you get the `ImportError`.

The cycle occurs at:

`servers/common/services/coin_pair_price_service.py` lines 10‑12, importing `OracleCoinPairService`

`servers/oracle/src/oracle_coin_pair_service.py` lines 6‑8, importing `CoinPairService/TasksRunnerService`

A fix is to break the dependency loop: the common module shouldn’t depend on oracle. Move the `CoinPairServiceType` enum (or equivalent identifier) into a shared module or directly into `coin_pair_price_service.py`, and have both modules import that shared enum without importing each other.


### Fix summary

Added a shared `CoinPairServiceType` enum in the common services package to centralize service role definitions and support reuse.

Updated the coin pair price service to import the shared enum and return service types without depending on the Oracle implementation, preventing circular imports.

Switched the Oracle coin pair service and loop logic to reference the shared enum while keeping existing service-type checks intact.
