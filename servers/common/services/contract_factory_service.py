import logging
import os

from moneyonchain import contract
from moneyonchain.manager import ConnectionManager

from common import settings, helpers
from common.services.blockchain import BlockChain, BlockChainContract, \
    parse_addr
from common.services.coin_pair_price_service import CoinPairService
from common.services.eternal_storage_service import EternalStorageService
from common.services.info_getter_service import InfoGetterService
from common.services.moc_token_service import MocTokenService
from common.services.staking_machine_service import StakingMachineService
from common.services.oracle_manager_service import OracleManagerService
from common.services.supporters_service import SupportersService


logger = logging.getLogger(__name__)


class ContractFactoryService:
    @staticmethod
    def get_contract_factory_service():
        if settings.MOC_NETWORK is not None:
            logger.info(
                "Using moneyonchain library for contracts abis and addresses")
            return MocContractFactoryService()
        else:
            logger.warning(
                "Using build dir development files for contracts abis and addresses!!!")
            return BuildDirContractFactoryService()

    def __init__(self, blockchain):
        self.blockchain = blockchain

    def get_blockchain(self):
        return self.blockchain

    def _get_contract(self, addr, abi):
        return BlockChainContract(self.blockchain, addr, abi)

    def get_coin_pair_price(self, addr) -> CoinPairService:
        raise Exception("Unimplemented")

    def get_eternal_storage(self, addr) -> EternalStorageService:
        raise Exception("Unimplemented")

    def get_moc_token(self, addr) -> MocTokenService:
        raise Exception("Unimplemented")

    def get_oracle_manager(self, addr) -> OracleManagerService:
        raise Exception("Unimplemented")

    def get_info_service(self, addr) -> InfoGetterService:
        raise Exception("Unimplemented")

    def get_supporters(self, addr) -> SupportersService:
        raise Exception("Unimplemented")

    def get_abi(self, name):
        raise Exception("Unimplemented")

    def get_addr(self, name):
        raise Exception("Unimplemented")


class MocContractFactoryService(ContractFactoryService):
    @property
    def abi_path(self):
        return os.path.join(
            os.path.dirname(os.path.realpath(contract.__file__)), "abi")

    @classmethod
    def PrepareBlockchainOptionsAddresses(cls):
        options = ConnectionManager.options_from_config()
        networks = options["networks"]
        network = settings.MOC_NETWORK
        if network not in networks:
            # in case of no network, fallback to "the-other" Factory..
            return BlockChain(settings.NODE_URL, settings.CHAIN_ID,
                                    settings.WEB3_TIMEOUT), None, None
            # raise Exception("Invalid moc network name %r. Available: %r" % (
            #                 network, networks.keys()))
        options = networks[network]
        addresses = options["addresses"]
        url = settings.NODE_URL if settings.NODE_URL is not None else options[
            "uri"]
        chain_id = settings.CHAIN_ID if settings.CHAIN_ID is not None else options["chain_id"]
        return BlockChain(url, chain_id, settings.WEB3_TIMEOUT), options, addresses

    def __init__(self):
        blockchain, self.options, self.addresses = self.PrepareBlockchainOptionsAddresses()
        ContractFactoryService.__init__(self, blockchain)

    def get_coin_pair_price(self, addr) -> CoinPairService:
        abi = self._read_abi('CoinPairPrice.abi')
        return CoinPairService(self._get_contract(addr, abi))

    def get_eternal_storage(self, addr) -> EternalStorageService:
        abi = self._read_abi('IRegistry.abi')
        return EternalStorageService(self._get_contract(addr, abi))

    def get_moc_token(self, addr) -> MocTokenService:
        abi = self._read_abi('DocToken.abi')
        return MocTokenService(self._get_contract(addr, abi))

    def get_oracle_manager(self, addr) -> OracleManagerService:
        abi = self._read_abi('OracleManager.abi')
        return OracleManagerService(self._get_contract(addr, abi))

    def get_info_service(self, addr) -> InfoGetterService:
        abi = self._read_abi('InfoGetter.abi')
        return InfoGetterService(self._get_contract(addr, abi))

    def get_supporters(self, addr) -> SupportersService:
        abi = self._read_abi('ISupporters.abi')
        return SupportersService(self._get_contract(addr, abi))

    def get_abi(self, name):
        return self._read_abi(name)

    def get_addr(self, name):
        if name == "ETERNAL_STORAGE" and "EternalStorageGobernanza" in self.addresses:
            return self.addresses["EternalStorageGobernanza"]
        return None

    def _read_abi(self, file_name):
        return contract.Contract.content_abi_file(
            os.path.join(self.abi_path, file_name))


class BuildDirContractFactoryService(ContractFactoryService):
    FILES = {
        "ETERNAL_STORAGE": "IRegistry.json",
        "MOC_ERC20": "IERC20.json",
        "STAKING_MACHINE": "IStakingMachine.json",
        "STAKING_MACHINE_ORACLES": "IStakingMachineOracles.json",
        "SUPPORTERS": "ISupporters.json",
        "ORACLE_MANAGER": "IOracleManager.json",
        "COIN_PAIR_PRICE": "ICoinPairPrice.json",
        "INFO_GETTER": "IOracleInfoGetter.json",
    }
    DATA = dict()

    def __init__(self):
        if settings.NODE_URL is None:
            raise Exception("NODE_URL env var must be configured")
        blockchain = BlockChain(settings.NODE_URL, settings.CHAIN_ID,
                                settings.WEB3_TIMEOUT)
        ContractFactoryService.__init__(self, blockchain)

    def get_coin_pair_price(self, addr) -> CoinPairService:
        data = self._read_data("COIN_PAIR_PRICE")
        return CoinPairService(self._get_contract(addr, data["abi"]))

    def get_eternal_storage(self, addr) -> EternalStorageService:
        data = self._read_data("ETERNAL_STORAGE")
        return EternalStorageService(self._get_contract(addr, data["abi"]))

    def get_moc_token(self, addr) -> MocTokenService:
        data = self._read_data("MOC_ERC20")
        return MocTokenService(self._get_contract(addr, data["abi"]))

    def get_staking_machine(self, addr) -> StakingMachineService:
        i_staking_data = self._read_data("STAKING_MACHINE")
        i_staking_oracles_data = self._read_data("STAKING_MACHINE_ORACLES")
        abi = i_staking_data['abi'] + i_staking_oracles_data['abi']
        return StakingMachineService(self._get_contract(addr, abi))

    def get_oracle_manager(self, addr) -> OracleManagerService:
        data = self._read_data("ORACLE_MANAGER")
        return OracleManagerService(self._get_contract(addr, data["abi"]))

    def get_info_service(self, addr) -> InfoGetterService:
        data = self._read_data("INFO_GETTER")
        return InfoGetterService(self._get_contract(addr, data["abi"]))

    def get_supporters(self, addr) -> SupportersService:
        data = self._read_data("SUPPORTERS")
        return SupportersService(self._get_contract(addr, data["abi"]))

    @classmethod
    def get_addr(cls, name):
        data = cls._read_data(name)
        networks = data["networks"]
        network_id = settings.DEVELOP_NETWORK_ID
        if len(networks) == 1:
            network_id = next(iter(networks))
        if network_id is None:
            raise Exception("Configure DEVELOP_NETWORK_ID environment variable")
        logger.info("Using network id %r for %s" % (network_id, name))
        return parse_addr(data["networks"][str(network_id)]["address"])

    @classmethod
    def get_abi(cls, name):
        data = cls._read_data(name)
        return data["abi"]

    @classmethod
    def _read_data(cls, name):
        if name in cls.DATA:
            return cls.DATA[name]
        if name not in cls.FILES:
            raise ValueError("Invalid file name %s " % name)
        data = helpers.readfile(settings.CONTRACT_FOLDER, cls.FILES[name])
        cls.DATA[name] = data
        return data
