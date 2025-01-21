import logging
from typing import List

from hexbytes import HexBytes

from common.services.blockchain import BlockChainAddress, BlockchainAccount, is_error, BlockChain
from common.services.coin_pair_price_service import CoinPairService
from common.services.info_getter_service import InfoGetterService
from common.services.oracle_dao import CoinPair, CoinPairInfo, RoundInfo, FullOracleRoundInfo, OracleBlockchainInfo
from common.services.oracle_manager_service import OracleManagerService
from common.services.signal_service import ConditionalPublishServiceBase


logger = logging.getLogger(__name__)


class OracleCoinPairService:
    def __init__(self, blockchain: BlockChain,
                 coin_pair_service: CoinPairService,
                 info_service: InfoGetterService,
                 oracle_manager_service: OracleManagerService,
                 coin_pair_info: CoinPairInfo):
        self._blockchain = blockchain
        self._coin_pair_service = coin_pair_service
        self._info_service = info_service
        self._oracle_manager_service = oracle_manager_service
        self._coin_pair_info = coin_pair_info
        self._signal_service = ConditionalPublishServiceBase.SyncCreate(blockchain, str(self.coin_pair))

    @property
    def signal(self) -> ConditionalPublishServiceBase:
        return self._signal_service

    @property
    def coin_pair(self) -> CoinPair:
        return self._coin_pair_info.coin_pair

    @property
    def addr(self) -> BlockChainAddress:
        return self._coin_pair_info.addr

    async def get_selected_oracles_info(self) -> List[FullOracleRoundInfo]:
        oracles = []
        round_info: RoundInfo = await self._coin_pair_service.get_round_info()
        if is_error(round_info):
            return round_info
        for addr in round_info.selectedOracles:
            info = await self.get_oracle_round_info(addr)
            if is_error(info):
                return info
            oracles.append(info)
        return oracles

    async def get_oracle_round_info(self, address: BlockChainAddress) -> FullOracleRoundInfo:
        registration_info = await self._oracle_manager_service.get_oracle_registration_info(address)
        if is_error(registration_info):
            return registration_info
        bc_data = await self._coin_pair_service.get_oracle_round_info(address)
        if is_error(bc_data):
            return bc_data
        return FullOracleRoundInfo(*registration_info, *bc_data)

    async def get_last_pub_block_hash(self, last_pub_block=None):
        if last_pub_block is None:
            last_pub_block = await self.get_last_pub_block()
        return (await self._blockchain.get_block_by_number(last_pub_block)).hash
        # return hashlib.sha3_256(str(last_pub_block).encode('ascii')).digest()

    async def get_price(self):
        return await self._coin_pair_service.get_price()

    async def get_lock_period_timestamp(self):
        round_info: RoundInfo = await self.get_round_info()
        return round_info.lockPeriodTimestamp

    async def get_max_oracles_per_rounds(self):
        return await self._coin_pair_service.get_max_oracles_per_rounds()

    async def can_remove_oracle(self, addr: BlockChainAddress):
        return await self._coin_pair_service.can_remove_oracle(addr)

    async def get_available_reward_fees(self):
        return await self._coin_pair_service.get_available_reward_fees()

    async def publish_price(self,
                            version,
                            coin_pair,
                            price,
                            oracle_addr,
                            blocknumber,
                            signatures,
                            account: BlockchainAccount = None,
                            wait=False,
                            last_gas_price=None):
        return await self._coin_pair_service.publish_price(version, coin_pair, price,
                                                           oracle_addr, blocknumber, signatures,
                                                           account=account, wait=wait, last_gas_price=last_gas_price)

    async def get_coin_pair(self) -> str:
        return await self._coin_pair_service.get_coin_pair()

    async def get_token_addr(self) -> str:
        return await self._coin_pair_service.get_token_addr()

    async def get_last_pub_block(self) -> int:
        return await self._coin_pair_service.get_last_pub_block()

    async def get_valid_price_period_in_blocks(self) -> int:
        return await self._coin_pair_service.get_valid_price_period_in_blocks()

    def is_info_service_available(self) -> bool:
        return self._info_service is not None

    async def get_oracle_server_info(self) -> OracleBlockchainInfo:
        data = await self._info_service.get_oracle_server_info(self._oracle_manager_service, self._coin_pair_service)
        if is_error(data):
            return data
        (round_number, start_block, lock_period_end_block, total_points,
         selected_oracles_info,
         current_price, current_block,
         last_publication_block, last_hash,
         valid_price_period_in_blocks
         ) = data
        if int.from_bytes(last_hash, byteorder='big') == 0:
            last_publication_block_hash = await self.get_last_pub_block_hash(last_publication_block)
        else:
            last_publication_block_hash = HexBytes(last_hash)
        s_oracles = []
        for so in selected_oracles_info:
            (stake, points, addr, owner, name) = so
            # Only selected in current round oracles are returned.
            s_oracles.append(FullOracleRoundInfo(addr, name, stake, owner, points, True, round_number))
        return OracleBlockchainInfo(self.coin_pair,
                                    s_oracles,
                                    current_price,
                                    current_block,
                                    last_publication_block,
                                    last_publication_block_hash,
                                    valid_price_period_in_blocks)

    async def get_round_info(self) -> RoundInfo:
        return await self._coin_pair_service.get_round_info()

    async def switch_round(self, account: BlockchainAccount = None, wait=False,
                           last_gas_price=None):       
        return await self._coin_pair_service.switch_round(account=account, wait=wait,
                           last_gas_price=last_gas_price)

    async def get_last_block_timestamp(self):
        data = await self._blockchain.get_last_block_data()
        return data["timestamp"]
