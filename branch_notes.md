# Notes related to the branch purpose

## Fixing circular import issue


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
