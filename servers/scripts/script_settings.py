import logging

from starlette.datastructures import Secret

from common.services.blockchain import BlockchainAccount, is_error
from common.services.contract_factory_service import BuildDirContractFactoryService, ContractFactoryService
from common.services.oracle_dao import CoinPair
from common.services.supporters_service import SupportersService
from common.settings import config
# https://www.starlette.io/config/
from oracle.src import oracle_settings
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_service import OracleService
from oracle.src.oracle_coin_pair_service import OracleCoinPairService

logger = logging.getLogger(__name__)

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
    coin_pairs = await oracle_service.oracle_manager_service.get_all_coin_pair()
    coin_pair_info = await oracle_service.oracle_manager_service.get_coin_pair_info(coin_pairs[0])
    oracle_coin_pair_service = OracleCoinPairService(cf.get_blockchain(),
                                                     cf.get_coin_pair_price(coin_pair_info.addr),
                                                     oracle_service.info_service,
                                                     oracle_service.oracle_manager_service,
                                                     coin_pair_info)
    addr = await oracle_coin_pair_service.get_token_addr()
    if is_error(addr):
        logger.error("ERROR GETTING TOKEN ADDR", addr)
        raise Exception(addr)
    moc_token_service = cf.get_moc_token(addr)
    staking_machine_service = cf.get_staking_machine(conf.STAKING_MACHINE_ADDR)
    oracle_manager_service = cf.get_oracle_manager(conf.ORACLE_MANAGER_ADDR)
    return oracle_manager_service, moc_token_service, staking_machine_service, conf.STAKING_MACHINE_ADDR


async def configure_supporter():
    cf = ContractFactoryService.get_contract_factory_service()
    conf = OracleConfiguration(cf)
    await conf.initialize()
    supporters_service = SupportersService(cf, conf)
    moc_token_service = cf.get_moc_token(await supporters_service.get_token_addr())
    return conf, supporters_service, moc_token_service
