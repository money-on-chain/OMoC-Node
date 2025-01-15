from common.services.blockchain import BlockChainContract
from common.services.contract_factory_service import MocContractFactoryService


class SignalService:
    ABI = [{
        "inputs": [],
        "name": "getlen",
        "outputs": [{
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }],
        "stateMutability": "view",
        "type": "function"
    }]

    def __init__(self):
        blockchain, _, _ = MocContractFactoryService.PrepareBlockchainOptionsAddresses()
        self.contract = BlockChainContract(blockchain,
                                           '0xD5746777FE34a3562aD3abc1501629ca0190F23B', self.ABI)

    async def getlen_call(self):
        return await self.contract.bc_call('getlen',)

