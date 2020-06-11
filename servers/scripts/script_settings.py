from starlette.datastructures import Secret

from common.services.blockchain import BlockchainAccount, BlockChainContract, BlockChainAddress
from common.services.contract_factory_service import BuildDirContractFactoryService, ContractFactoryService
from common.services.oracle_dao import CoinPair
from common.services.supporters_service import SupportersDetailedBalance
from common.settings import config
# https://www.starlette.io/config/
from oracle.src import oracle_settings
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_service import OracleService

USE_COIN_PAIR = [CoinPair("BTCUSD"), CoinPair("RIFBTC")]
INITIAL_STAKE = 5 * (10 ** 12)
NEEDED_GAS = 5 * (10 ** 12)
REWARDS = 123

SCRIPT_ORACLE_OWNER_ACCOUNT = BlockchainAccount(config('SCRIPT_ORACLE_OWNER_ADDR', cast=str),
                                                config('SCRIPT_ORACLE_OWNER_PRIVATE_KEY', cast=Secret))
SCRIPT_REWARD_BAG_ACCOUNT = BlockchainAccount(config('SCRIPT_REWARD_BAG_ADDR', cast=str),
                                              config('SCRIPT_REWARD_BAG_PRIVATE_KEY', cast=Secret))
SCRIPT_ORACLE_ACCOUNT = oracle_settings.get_oracle_account()

NEEDED_APROVE_BAG = 1000000000000000

cf = BuildDirContractFactoryService()
blockchain = cf.blockchain


async def configure_oracle():
    cf = ContractFactoryService.get_contract_factory_service()
    conf = OracleConfiguration(cf)
    await conf.initialize()
    oracle_service = OracleService(cf, conf.ORACLE_MANAGER_ADDR, conf.INFO_ADDR)
    moc_token_service = cf.get_moc_token(await oracle_service.get_token_addr())
    oracle_manager_service = cf.get_oracle_manager(conf.ORACLE_MANAGER_ADDR)
    oracle_manager_addr = cf.get_addr("ORACLE_MANAGER")
    return conf, oracle_service, moc_token_service, oracle_manager_service, oracle_manager_addr


class SupportersVestedService:
    def __init__(self, cf: ContractFactoryService, conf: OracleConfiguration):
        self.vested_addr = conf.SUPPORTERS_VESTED_ADDR
        self.supporters_service = cf.get_supporters(conf.SUPPORTERS_ADDR)
        self._contract = BlockChainContract(cf.get_blockchain(),
                                            self.vested_addr,
                                            cf.get_abi("SUPPORTERS_VESTED"))

    async def supporters_call(self, method, *args, **kw):
        return await self._contract.bc_call(method, *args, **kw)

    async def supporters_execute(self, method, *args, account: BlockchainAccount = None, wait=False, **kw):
        return await self._contract.bc_execute(method, *args, account=account, wait=wait, **kw)

    async def detailed_balance_of(self, addr: BlockChainAddress) -> SupportersDetailedBalance:
        return await self.supporters_service.vesting_info_of(self.vested_addr, addr)

    async def add_stake(self, mocs: int, account: BlockchainAccount = None, wait=False):
        return await self.supporters_execute("addStake", mocs, account=account, wait=wait)

    async def stop(self, account: BlockchainAccount = None, wait=False):
        return await self.supporters_execute("stop", account=account, wait=wait)

    async def withdraw(self, account: BlockchainAccount = None, wait=False):
        return await self.supporters_execute("withdraw", account=account, wait=wait)

    async def get_token_addr(self) -> SupportersDetailedBalance:
        return await self.supporters_service.get_token_addr()

    async def is_ready_to_distribute(self) -> SupportersDetailedBalance:
        return await self.supporters_service.is_ready_to_distribute()

    async def distribute(self, account: BlockchainAccount = None, wait=False) -> SupportersDetailedBalance:
        return await self.supporters_service.distribute(account=account, wait=wait)


async def configure_supporter():
    cf = ContractFactoryService.get_contract_factory_service()
    conf = OracleConfiguration(cf)
    await conf.initialize()
    supporters_service = SupportersVestedService(cf, conf)
    moc_token_service = cf.get_moc_token(await supporters_service.get_token_addr())
    return conf, supporters_service, moc_token_service
