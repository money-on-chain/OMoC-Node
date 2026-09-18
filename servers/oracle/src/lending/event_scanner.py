from eth_abi import decode_abi
from eth_utils import keccak
from hexbytes import HexBytes
from web3 import Web3

EVENT_TOPIC = keccak(
    text="VaultStateUpdated(address,address,address,uint256,uint256,bool)"
).hex()


def _hex(value):
    return value.hex() if hasattr(value, "hex") else str(value)


def _address(topic):
    raw = _hex(topic)
    if raw.startswith("0x"):
        raw = raw[2:]
    return "0x" + raw[-40:].lower()


class LendingEventScanner:
    def __init__(self, blockchain, manager):
        self.blockchain = blockchain
        self.manager = Web3.toChecksumAddress(manager)

    async def scan(self, from_block, to_block):
        try:
            logs = await self.blockchain.get_logs(
                {
                    "address": self.manager,
                    "fromBlock": from_block,
                    "toBlock": to_block,
                    "topics": ["0x" + EVENT_TOPIC],
                }
            )
        except Exception:
            if from_block >= to_block:
                raise
            middle = (from_block + to_block) // 2
            left = await self.scan(from_block, middle)
            right = await self.scan(middle + 1, to_block)
            return left + right
        events = [self.decode(log) for log in logs]
        events.sort(
            key=lambda event: (
                event["block_number"],
                event["transaction_index"],
                event["log_index"],
            )
        )
        return events

    @staticmethod
    def decode(log):
        topics = log["topics"]
        ac_balance, credit_units, liquidating = decode_abi(
            ["uint256", "uint256", "bool"], HexBytes(log["data"])
        )
        return {
            "chain_id": None,
            "transaction_hash": _hex(log["transactionHash"]),
            "log_index": log["logIndex"],
            "block_number": log["blockNumber"],
            "block_hash": _hex(log["blockHash"]),
            "transaction_index": log["transactionIndex"],
            "user": _address(topics[1]),
            "tp_token": _address(topics[2]),
            "moc_bucket": _address(topics[3]),
            "ac_balance": ac_balance,
            "credit_units": credit_units,
            "liquidating": liquidating,
        }
