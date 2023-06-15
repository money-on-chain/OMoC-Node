import asyncio
import logging
import traceback
import typing

from common import settings
from decorator import decorator
from eth_typing import Primitives, HexStr
from pydantic import AnyHttpUrl
from starlette.datastructures import Secret
from web3 import Web3, HTTPProvider
from web3.exceptions import TransactionNotFound

from common.bg_task_executor import BgTaskExecutor
from common.helpers import dt_now_at_utc

logger = logging.getLogger(__name__)

ZERO_ADDR = "0x0000000000000000000000000000000000000000"


def keccak256(text: str = None, hexstr: HexStr = None, primitive: Primitives = None):
    return Web3.keccak(primitive=primitive, text=text, hexstr=hexstr)


def parse_addr(addr):
    return Web3.toChecksumAddress(addr)


class STATE:
    PENDING, SUCCESS, FAILED, ERROR = 'pending', 'success', 'failed', 'error'


BCSuccess = typing.NamedTuple("BCSuccess", [("state", STATE), ("hash", str)])


class BCError(typing.NamedTuple("BCError", [("state", STATE), ("hash", str),
                                            ("error", str)])):
    def __new__(cls, err, hash):
        if err.startswith("Could not decode") and "return data b'\\x00'" in err:
            err = "Check your NODE_URL configuration, most probably we are using the wrong block chain node : " + err
        return super(BCError, cls).__new__(cls, STATE.ERROR, hash, err)

    @classmethod
    def Get(cls, err):
        return cls(str(err), None)


def is_error(tx):
    return isinstance(tx, BCError)


async def run_in_executor(func):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func)


@decorator
async def exec_with_catch_async(f, *arg, **kw):
    try:
        return await f(*arg, **kw)
    except asyncio.CancelledError as e:
        raise e
    except Exception as err:
        logger.debug(traceback.format_exc())
        return BCError.Get(err)


class BlockChainAddress(AnyHttpUrl):
    @classmethod
    def __get_validators__(cls) -> 'CallableGenerator':
        yield cls.validate

    @classmethod
    def validate(cls, v) -> str:
        if not isinstance(v, str):
            raise ValueError(f'strict string: str expected not {type(v)}')
        return parse_addr(v.lower())


class BlockchainAccount(typing.NamedTuple('BlockchainAccount', [('addr', str),
                                          ('key', Secret)])):
    def __new__(cls, addr, key):
        addr = parse_addr(addr.lower())
        if not isinstance(key, Secret):
            raise Exception("Key must be secret")
        skey = str(key)
        if skey.startswith("0x"):
            skey = skey[2:]
        return super(BlockchainAccount, cls).__new__(cls, addr, Secret(skey))


class BlockChainPK(AnyHttpUrl):
    @classmethod
    def __get_validators__(cls) -> 'CallableGenerator':
        yield cls.validate

    @classmethod
    def validate(cls, v) -> str:
        if not isinstance(v, str):
            raise ValueError(f'strict string: str expected not {type(v)}')
        return Web3.eth.account.from_key(v).key


class BlockchainStateLoop(BgTaskExecutor):
    def __init__(self, conf):
        logger.debug('initializing BlockchainStateLoop')
        self.conf = conf
        self.gas_calc = GasCalculator()
        super().__init__(name="BlockchainStateLoop", main=self.run)

    async def run(self):
        logger.info("BlockchainStateLoop loop start")
        await self.gas_calc.update()
        logger.info("BlockchainStateLoop loop done")
        return self.conf.ORACLE_BLOCKCHAIN_STATE_DELAY 


class GasCalculator:

    def __init__(self):

        logger.info('Initializing GasCalculator ...')

        def get(var_name, show_fnc=repr):
            value = getattr(settings, var_name)
            logger.info(f"    Getting parameter {repr(var_name)} -> {show_fnc(value)}")
            return value

        self.node_url = str(get('NODE_URL', str))
        self.default_gas_price = get('DEFAULT_GAS_PRICE')
        self.gas_percentage_admitted = get('GAS_PERCENTAGE_ADMITTED')
        self.gas_price_hard_limit_min = get('GAS_PRICE_HARD_LIMIT_MIN')
        self.gas_price_hard_limit_max = get('GAS_PRICE_HARD_LIMIT_MAX')
        self.gas_price_hard_limit_multiplier = get('GAS_PRICE_HARD_LIMIT_MULTIPLIER')

        self.last_price = None 

        self.W3 = Web3(HTTPProvider(self.node_url,
                                    request_kwargs={'timeout': settings.WEB3_TIMEOUT}))

    def set_last_price(self, gas_price):
        self.last_price = gas_price

    def get_gas_price_plus_x_perc(self, gas_price):
        return gas_price + gas_price * (self.gas_percentage_admitted / 100)

    def get_last_price(self):
        if self.last_price is None:
            return self.default_gas_price
        return int(self.get_gas_price_plus_x_perc(self.last_price))

    def is_gas_price_out_of_range(self, gas_price):
        if gas_price > self.get_last_price():
            return True
        return False

    @exec_with_catch_async
    async def get_current(self):

        gas_price = await run_in_executor(lambda: self.W3.eth.gasPrice)
        
        if gas_price is None:
            gas_price = self.get_last_price() if self.get_last_price() is not None else self.default_gas_price
        
        if self.is_gas_price_out_of_range(gas_price):
            gas_price = self.get_last_price()

        gas_price = gas_price * self.gas_price_hard_limit_multiplier
        
        if self.gas_price_hard_limit_min > gas_price:
            gas_price = self.gas_price_hard_limit_min
        
        if self.gas_price_hard_limit_max and self.gas_price_hard_limit_max < gas_price:
            gas_price = self.gas_price_hard_limit_max
        
        self.set_last_price(gas_price)
        return gas_price
    
    async def update(self):
        await self.get_current()


class BlockChain:
    def __init__(self, node_url, chain_id, timeout):
        self.chain_id = chain_id
        self.latest_block = None
        self.latest_block_at = None
        self.W3 = Web3(HTTPProvider(str(node_url),
                                    request_kwargs={'timeout': timeout}))

    def get_contract(self, addr, abi):
        return self.W3.eth.contract(address=parse_addr(addr), abi=abi)

    def sign_transaction(self, txn, private_key):
        return self.W3.eth.account.sign_transaction(txn, private_key)

    async def send_raw_transaction(self, raw_transaction: HexStr):
        return await run_in_executor(lambda: self.W3.eth.sendRawTransaction(raw_transaction))

    @exec_with_catch_async
    async def get_last_block(self):
        return await run_in_executor(lambda: self.W3.eth.blockNumber)

    @exec_with_catch_async
    async def get_last_block_data(self):
        block = await run_in_executor(lambda: self.W3.eth.getBlock("latest"))
        self.latest_block = block
        self.latest_block_at = dt_now_at_utc()
        return block

    @exec_with_catch_async
    async def get_block_by_number(self, block_number, full=False):
        return await run_in_executor(lambda: self.W3.eth.getBlock(block_number, full))
    
    async def get_tx(self, method, account_addr: str, gas_price):
        logger.debug(f"+++++++++ get tx ++++++++ {str(account_addr)} - {method}")
        from_addr = parse_addr(str(account_addr))

        nonce = await run_in_executor(lambda: self.W3.eth.getTransactionCount(
                                                                    from_addr))
        logger.debug(f"Nonce: {nonce}  sender: {from_addr}")
        try:
            logger.debug("GAS: %r" % gas_price)
            gas = await run_in_executor(lambda: method.estimateGas({'from': from_addr,
                                                                    'gasPrice': gas_price,
                                                                    'nonce': nonce}))
        except asyncio.CancelledError as e:
            raise e
        except Exception as err:
            logger.debug("USING DEFAULT VALUE FOR GAS LIMIT")
            gas = 4200000  # adji: Must be enough, can't be to close to gas lim.

        chain_id = await run_in_executor(lambda: self.W3.eth.chainId)
        if not chain_id:
            chain_id = self.chain_id
        if not chain_id:
            raise Exception("Can't get chain id from block chain, must be configured")
        data = {'from': from_addr,
                'chainId': chain_id,
                'gasPrice': gas_price,
                'gas': gas,
                'nonce': nonce}

        txn = method.buildTransaction(data)
        return {"tx": txn, "txdata": data}

    @exec_with_catch_async
    async def bc_transfer(self, to_addr: str, amount: int, account: BlockchainAccount = None, wait=False):
        from_addr = parse_addr(account.addr)
        nonce = await run_in_executor(lambda: self.W3.eth.getTransactionCount(from_addr))
        txn = {'from': from_addr,
               # 'chainId': W3.eth.chainId,
               'gasPrice': self.W3.eth.gasPrice,
               'gas': 21000,
               'nonce': nonce,
               'to': parse_addr(to_addr),
               'value': amount,
               'data': b'',
               }
        signed_txn = self.W3.eth.account.sign_transaction(txn, private_key=Web3.toBytes(hexstr=str(account.key)))
        tx = await run_in_executor(lambda: self.W3.eth.sendRawTransaction(signed_txn.rawTransaction))
        return await self.process_tx(tx, wait)

    async def process_tx(self, tx, wait):
        if isinstance(tx, dict) and "error" in tx:
            logger.error("TX ERROR", tx)
            return BCError(STATE.ERROR, tx)
        if wait:
            logger.debug("return_tx %r", tx)
            ret = await self.get_receipt(tx, wait)
            logger.debug("return_tx %r receipt %r", tx, ret)
            if isinstance(ret, dict) and "error" in ret:
                return BCError(STATE.ERROR, ret, tx)
            return BCSuccess(ret['state'], tx)
        return BCSuccess(STATE.SUCCESS, tx)

    @exec_with_catch_async
    async def get_balance(self, addr: BlockChainAddress):
        return await run_in_executor(lambda: self.W3.eth.getBalance(addr))

    async def get_receipt(self, txhash: str, wait: bool = False, timeout=60 * 10, poll_latency=0.1):
        if wait:
            async def run_with_timeout():
                while True:
                    try:
                        receipt = await run_in_executor(lambda: self.W3.eth.getTransactionReceipt(txhash))
                        if receipt is not None and receipt['blockHash'] is not None:
                            return receipt
                    except TransactionNotFound:
                        pass
                    await asyncio.sleep(1)  # poll_latency)

            receipt = await asyncio.wait_for(run_with_timeout(), timeout=timeout)
            # receipt = await loop.run_in_executor(None, lambda: W3.eth.waitForTransactionReceipt(txhash, timeout=timeout,
            #                                                                                    poll_latency=poll_latency))
        else:
            receipt = await run_in_executor(lambda: self.W3.eth.getTransactionReceipt(txhash))
        if not receipt:
            return {'tx': txhash, 'state': STATE.PENDING}
        return {'tx': receipt.transactionHash.hex(),
                'block': receipt.blockHash.hex(),
                'gasUsed': receipt.gasUsed,
                'status': receipt.status,
                'state': (STATE.SUCCESS if receipt.status != 0 else STATE.FAILED)}


class BlockChainContract:
    def __init__(self, blockchain: BlockChain, addr, abi):
        self._addr = addr
        self._blockchain = blockchain
        self._contract = blockchain.get_contract(addr, abi)

    @property
    def addr(self):
        return self._addr

    @exec_with_catch_async
    async def bc_call(self, method, *args, account: BlockchainAccount = None, **kw):
        return await run_in_executor(lambda: self._contract.functions[method](*args, **kw).call(
            {'from': account} if account else {}))

    @exec_with_catch_async
    async def bc_execute(self, method, *args, account: BlockchainAccount = None, wait=False, last_gas_price=None, **kw):
        if not account:
            raise Exception("Missing key, cant execute")
        method_func = self._contract.functions[method](*args, **kw)
        tx = await self._blockchain.get_tx(method_func, str(account.addr), gas_price=last_gas_price)
        txn = tx["tx"]
        signed_txn = self._blockchain.sign_transaction(txn, private_key=Web3.toBytes(hexstr=str(account.key)))
        logger.debug("%s SENDING SIGNED TX %r", tx["txdata"]["chainId"], signed_txn)
        logger.debug(f"--+Blockchain ID {id(self._blockchain)}")
        logger.debug("--+Nonce %s", tx["txdata"]["nonce"])
        tx = await self._blockchain.send_raw_transaction(signed_txn.rawTransaction)
        return await self._blockchain.process_tx(tx, wait)
