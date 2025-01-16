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


class SignalService:
    MULTICALL_ADDR = '0x6FdB1c9e1a1A8beD2EE22a3d5E62CA330ee88ecb'
    SIGNAL_ADDRESS = '0xD5746777FE34a3562aD3abc1501629ca0190F23B'.lower()
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

    def __init__(self):
        self.last_value = self.last_block = None
        self.blockchain, _, _ = MocContractFactoryService.PrepareBlockchainOptionsAddresses()

    @property
    def w3(self):
        return self.blockchain.W3

    def sync_fetch(self):
        w3_multicall = MulticallWBlock(self.w3)
        w3_multicall.add(W3Multicall.Call(self.SIGNAL_ADDRESS, self.SIGNAL_SIGNATURE))
        w3_multicall.address = self.MULTICALL_ADDR
        results = w3_multicall.callWBlock()
        self.last_value, self.last_block = results[0][0], results[1]

    async def getlen_call(self):
        await run_in_executor(self.sync_fetch)
        return self.tuple_value

    @property
    def tuple_value(self):
        return (self.last_value, self.last_block) if self.is_running else None

    @property
    def is_running(self):
        return self.last_block is not None

    async def is_paused(self):
        if self.is_running:
            return self.last_value==0
        return False

