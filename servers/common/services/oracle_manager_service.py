import logging
from typing import List

from common.services.blockchain import BlockChainAddress, BlockchainAccount, is_error, BlockChainContract
from common.services.oracle_dao import CoinPair, CoinPairInfo, OracleRegistrationInfo

logger = logging.getLogger(__name__)


class OracleManagerService:
    def __init__(self, contract: BlockChainContract):
        self._contract = contract

    @property
    def addr(self):
        return self._contract.addr

    async def oracle_manager_call(self, method, *args, **kw):
        return await self._contract.bc_call(method, *args, **kw)

    async def oracle_manager_execute(self, method, *args, account: BlockchainAccount = None, wait=False, **kw):
        return await self._contract.bc_execute(method, *args, account=account, wait=wait, **kw)

    async def get_token_addr(self):
        return await self.oracle_manager_call("token")

    async def get_min_coin_pair_subscription_stake(self):
        return await self.oracle_manager_call("getMinCPSubscriptionStake")

    async def register_oracle(self, address: BlockChainAddress, name: str, stake: int,
                              account: BlockchainAccount = None,
                              wait=False):
        return await self.oracle_manager_execute("registerOracle", address, name, account=account, wait=wait)

    async def subscribe_coin_pair(self, coin_pair: CoinPair, address: BlockChainAddress,
                                  account: BlockchainAccount = None,
                                  wait=False):
        return await self.oracle_manager_execute("subscribeCoinPair", address, coin_pair.longer(), account=account,
                                                 wait=wait)

    async def unsubscribe_coin_pair(self, coin_pair: CoinPair, address: BlockChainAddress,
                                    account: BlockchainAccount = None,
                                    wait=False):
        return await self.oracle_manager_execute("unsubscribeCoinPair", address, coin_pair.longer(), account=account,
                                                 wait=wait)

    async def is_subscribed(self, coin_pair: CoinPair, address: BlockChainAddress) -> bool:
        return await self.oracle_manager_call("isSubscribed", address, coin_pair.longer())

    async def can_remove(self, address: BlockChainAddress) -> bool:
        return await self.oracle_manager_call("canRemoveOracle", address)

    async def get_oracle_owner(self, address: BlockChainAddress) -> BlockChainAddress:
        return await self.oracle_manager_call("getOracleOwner", address)

    async def get_registered_oracles_len(self):
        return await self.oracle_manager_call("getRegisteredOraclesLen")

    async def get_registered_oracle_at_index(self, idx: int):
        return await self.oracle_manager_call("getRegisteredOracleAtIndex", idx)

    async def set_oracle_name(self, address: BlockChainAddress, name: str, account: BlockchainAccount = None,
                              wait=False):
        return await self.oracle_manager_execute("SetOracleName", address, name, account=account, wait=wait)

    async def is_oracle_registered(self, address: BlockChainAddress):
        return await self.oracle_manager_call("isOracleRegistered", address)

    async def get_oracle_registration_info(self, address: BlockChainAddress) -> OracleRegistrationInfo:
        bc_data = await self.oracle_manager_call("getOracleRegistrationInfo", address)
        if is_error(bc_data):
            return bc_data
        return OracleRegistrationInfo(address, *bc_data)

    async def remove_oracle(self, address: BlockChainAddress, account: BlockchainAccount = None, wait=False):
        return await self.oracle_manager_execute("removeOracle", address, account=account, wait=wait)

    async def get_coin_pair_info(self, coin_pair: CoinPair) -> CoinPairInfo:
        bc_data = await self.oracle_manager_call("getContractAddress", coin_pair.longer())
        if is_error(bc_data):
            return bc_data
        return CoinPairInfo(coin_pair, bc_data)

    async def get_all_coin_pair(self) -> List[CoinPair]:
        bc_count = await self.oracle_manager_call("getCoinPairCount")
        if is_error(bc_count):
            return bc_count
        ret = []
        for i in range(bc_count):
            bc_data = await self.oracle_manager_call("getCoinPairAtIndex", i)
            if is_error(bc_data):
                return bc_data
            ret.append(CoinPair(bc_data.decode("ascii")))
        return ret
