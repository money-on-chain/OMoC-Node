import logging
from typing import List

from common.services.blockchain import BlockChainAddress, BlockchainAccount, is_error, BlockChainContract
from common.services.oracle_dao import CoinPair, CoinPairInfo, OracleRegistrationInfo

logger = logging.getLogger(__name__)


class StakingMachineService:

    def __init__(self, contract: BlockChainContract):
        self._contract = contract

    @property
    def addr(self):
        return self._contract.addr

    async def staking_machine_call(self, method, *args, **kw):
        return await self._contract.bc_call(method, *args, **kw)

    async def staking_machine_execute(self, method, *args, account: BlockchainAccount = None, wait=False, **kw):
        return await self._contract.bc_execute(method, *args, account=account, wait=wait, **kw)

    async def get_supporters_addr(self):
        return await self.staking_machine_call("supporters")

    async def get_oracle_manager_addr(self):
        return await self.staking_machine_call("oracleManager")

    async def get_token_addr(self):
        return await self.staking_machine_call("mocToken")

    async def get_delay_machine_addr(self):
        return await self.staking_machine_call("delayMachine")

    async def get_withdraw_lock_time_addr(self):
        return await self.staking_machine_call("withdrawLockTime")

    async def get_total_mocs(self):
        return await self.staking_machine_call("totalMoc")

    async def get_total_tokens(self):
        return await self.staking_machine_call("totalToken")

    async def get_balance(self):
        return await self.staking_machine_call("getBalance")

    async def get_locked_balance(self):
        return await self.staking_machine_call("getLockedBalance")

    async def get_registered_oracles_length(self):
        return await self.staking_machine_call("getRegisteredOraclesLen")

    async def get_registered_oracle_at_index(self, index: int):
        return await self.staking_machine_call("getRegisteredOracleAtIndex", index)

    async def get_coin_pair_count(self):
        return await self.staking_machine_call("getCoinPairCount")

    async def get_coin_pair_at_index(self, index: int) -> CoinPair:
        return await self.staking_machine_call("getCoinPairAtIndex", index)

    async def get_contract_address(self, coin_pair: CoinPair) -> BlockChainAddress:
        return await self.staking_machine_call("getContractAddress", coin_pair)

    async def get_coin_pair_index(self, coin_pair: CoinPair, hint: int) -> int:
        return await self.staking_machine_call("getCoinPairIndex", coin_pair, hint)



    async def lock_mocs(self, moc_holder: BlockChainAddress, until_timestamp: int,
                              account: BlockchainAccount = None,
                              wait=False):
        return await self.staking_machine_execute("lockMocs", moc_holder, until_timestamp, account=account, wait=wait)

    async def deposit(self, mocs: int, destination: BlockChainAddress,
                              account: BlockchainAccount = None,
                              wait=False):
        return await self.staking_machine_execute("deposit", mocs, destination, account=account, wait=wait)

    async def deposit_from(self, mocs: int, destination: BlockChainAddress, source: BlockChainAddress,
                              account: BlockchainAccount = None,
                              wait=False):
        return await self.staking_machine_execute("depositFrom", mocs, destination, source, account=account, wait=wait)

    async def withdraw(self, mocs: int,
                              account: BlockchainAccount = None,
                              wait=False):
        return await self.staking_machine_execute("withdraw", mocs, account=account, wait=wait)

    async def register_oracle(self, oracle_addr: BlockChainAddress, name: str,
                              account: BlockchainAccount = None,
                              wait=False):
        return await self.staking_machine_execute("registerOracle", oracle_addr, name, account=account, wait=wait)

    async def set_oracle_name(self, name: str, account: BlockchainAccount = None,
                              wait=False):
        return await self.staking_machine_execute("setOracleName", name, account=account, wait=wait)

    async def is_oracle_registered(self, owner_addr: BlockChainAddress):
        return await self.staking_machine_call("isOracleRegistered", owner_addr)

    async def can_remove_oracle(self, owner_addr: BlockChainAddress) -> bool:
        return await self.staking_machine_call("canRemoveOracle", owner_addr)

    async def remove_oracle(self, account: BlockchainAccount = None, wait=False):
        return await self.staking_machine_execute("removeOracle", account=account, wait=wait)

    async def subscribe_to_coin_pair(self, coin_pair: CoinPair,
                                  account: BlockchainAccount = None,
                                  wait=False):
        return await self.staking_machine_execute("subscribeToCoinPair", coin_pair.longer(), account=account,
                                                 wait=wait)

    async def unsubscribe_from_coin_pair(self, coin_pair: CoinPair,
                                    account: BlockchainAccount = None,
                                    wait=False):
        return await self.staking_machine_execute("unSubscribeFromCoinPair", coin_pair.longer(), account=account,
                                                 wait=wait)

    async def is_subscribed(self, owner_addr: BlockChainAddress, coin_pair: CoinPair) -> bool:
        return await self.staking_machine_call("isSubscribed", owner_addr, coin_pair.longer())
