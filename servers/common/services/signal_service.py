from typing import Optional

from eth_typing import BlockIdentifier

from common.services.blockchain import run_in_executor
from common.services.contract_factory_service import MocContractFactoryService
from w3multicall.multicall import W3Multicall
from w3multicall.multicall import _decode_output, _unpack_aggregate_outputs, _encode_data


class MulticallWBlock(W3Multicall):
    def callWBlock(self, block_identifier: Optional[BlockIdentifier] = None) -> [list, int]:
        args = self._get_args()
        data = _encode_data(W3Multicall.MULTICALL_SELECTOR, W3Multicall.MULTICALL_INPUT_TYPES, args)
        eth_call_params = {
            'to': self.address,
            'data': data
        }
        rpc_response = self.web3.eth.call(eth_call_params, block_identifier=block_identifier)
        aggregated = _decode_output(rpc_response, W3Multicall.MULTICALL_OUTPUT_TYPES)
        unpacked = _unpack_aggregate_outputs(aggregated[1])
        outputs = []
        for call, (success, output) in zip(self.calls, unpacked):
            call_output = _decode_output(output, call.output_types, None, True)
            outputs.append(call_output)
        return outputs, aggregated[0]

# LockModule#Lock - 0x6AB47d47cF45C4aaA5c7F33c6632390674EfA294
# Multicall3Module#Multicall3 - 0x9a74f110586971345A396C74228094A04f5A5eA6

class SignalService:
    MULTICALL_ADDR = '0x9a74f110586971345A396C74228094A04f5A5eA6'
    SIGNAL_ADDRESS = '0x6AB47d47cF45C4aaA5c7F33c6632390674EfA294'.lower()
    SIGNAL_SIGNATURE = 'getlen()(uint)'
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

    def __init__(self, blockchain, cp):
        self.cp = cp
        self.blockchain = blockchain
        self.last_value = self.last_block = None
        self.last_pub = None
        # self.blockchain, _, _ = MocContractFactoryService.PrepareBlockchainOptionsAddresses()

    @property
    def w3(self):
        return self.blockchain.W3

    def sync_fetch(self):
        w3_multicall = MulticallWBlock(self.w3)
        w3_multicall.add(W3Multicall.Call(self.SIGNAL_ADDRESS, self.SIGNAL_SIGNATURE))
        w3_multicall.address = self.MULTICALL_ADDR
        results = w3_multicall.callWBlock()
        self.last_value, self.last_block = results[0][0], results[1]
        if self.is_paused():
            self.last_pub = self.last_block

    async def getlen_call(self):
        await run_in_executor(self.sync_fetch)
        return self.tuple_value

    @property
    def tuple_value(self):
        return (self.last_value, self.last_block) if self.is_running else None

    @property
    def is_running(self):
        return self.last_block is not None

    def is_paused(self):
        if self.is_running:
            return self.last_value==0
        return False

    def max_pub_block(self, blockchain_last_pub_block: int):
        if self.is_paused():
            if not (self.last_pub is None):
                return max(blockchain_last_pub_block, self.last_pub)
        return blockchain_last_pub_block