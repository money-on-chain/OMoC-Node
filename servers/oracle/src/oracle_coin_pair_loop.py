import asyncio
import json
import logging
import time
import traceback
import typing

import urllib3
from aiohttp import ClientConnectorError, InvalidURL, ClientResponseError
from hexbytes import HexBytes

from common import crypto, settings, helpers
from common.bg_task_executor import BgTaskExecutor
from common.crypto import verify_signature
from common.helpers import MyCfgdLogger
from common.services.blockchain import is_error, BlockchainStateLoop
from common.services.signal_service import SignalService
from oracle.src import monitor, oracle_settings
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfoLoop
from oracle.src.oracle_coin_pair_service import OracleCoinPairService, FullOracleRoundInfo
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_publish_message import PublishPriceParams
from oracle.src.oracle_turn import OracleTurn
from oracle.src.price_feeder.price_feeder import PriceFeederLoop

logger = logging.getLogger(__name__)

OracleSignature = typing.NamedTuple("OracleSignature",
                                    [("addr", str),
                                     ('signature', HexBytes)])


class OracleCoinPairLoop(BgTaskExecutor, MyCfgdLogger):
    def __init__(self, conf: OracleConfiguration,
                 cps: OracleCoinPairService,
                 price_feeder_loop: PriceFeederLoop,
                 vi_loop: OracleBlockchainInfoLoop,
                 bs_loop: BlockchainStateLoop,
                 ):
        self.bs_loop = bs_loop
        self._conf = conf
        self._oracle_addr = oracle_settings.get_oracle_account().addr
        self._oracle_addr_med = oracle_settings.get_oracle_account().med
        self._oracle_addr_short = oracle_settings.get_oracle_account().short
        self._cps = cps
        self._coin_pair = cps.coin_pair
        self._oracle_turn = OracleTurn(self._conf, cps.coin_pair)
        self._price_feeder_loop = price_feeder_loop
        self.vi_loop = vi_loop
        self.signal = SignalService()
        MyCfgdLogger.__init__(self,': ', self._coin_pair, self._oracle_addr_short)
        BgTaskExecutor.__init__(self, name="OracleCoinPairLoop-%s" % self._coin_pair, main=self.run)

    async def run(self):
        self.debug("OracleCoinPairLoop start")
        #logger.debug(f"--+OracleCoinPairLoop ID {id(self)}")
        round_info = await self._cps.get_round_info()
        if is_error(round_info):
            self.error(f"ERROR getting round info {repr(round_info)}")
            return self._conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL

        if round_info.round == 0:
            self.info(f"OCPL:Waiting for the initial round...")
            return self._conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL

        exchange_price = await self._price_feeder_loop.get_last_price(time.time(), True)
        if not exchange_price or exchange_price.ts_utc <= 0:
            self.info(f"Still don't have a valid price {exchange_price}")
            return self._conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL

        blockchain_info = self.vi_loop.get()
        if not blockchain_info:
            self.info(f"waiting for blockchain info")
            return self._conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL

        if self._oracle_turn.is_oracle_turn(blockchain_info, self._oracle_addr, exchange_price):
            signals = await self.signal.getlen_call()
            inibido = self.signal.is_paused()
            XX = 'ok' if not inibido else 'XX'
            self.info("---[%s %s]----> Is my turn I'm chosen: %s block %r, %r, %r" %
                        (repr(signals), XX, self._oracle_addr_med, blockchain_info.block_num,
                         blockchain_info.last_pub_block, blockchain_info.last_pub_block_hash.hex()))
            if not inibido:
                publish_success = await self.publish(blockchain_info.selected_oracles,
                                                     PublishPriceParams(self._conf.MESSAGE_VERSION,
                                                                        self._coin_pair,
                                                                        exchange_price,
                                                                        self._oracle_addr,
                                                                        blockchain_info.last_pub_block))
                if not publish_success:
                    # retry immediately.
                    return 1
        else:
            signals = repr(await self.signal.getlen_call())
            self.info("----%s-----> Is NOT my turn: %s block %r, %r, %r" %
                        (signals, self._oracle_addr_med, blockchain_info.block_num,
                         blockchain_info.last_pub_block, blockchain_info.last_pub_block_hash.hex()))
        return self._conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL

    async def publish(self, oracles, params: PublishPriceParams):
        message = params.prepare_price_msg()
        signature = crypto.sign_message(hexstr="0x" + message, account=oracle_settings.get_oracle_account())
        self.debug(f"we {self._oracle_addr_med} GOT MESSAGE {message}")
        self.info(f"we {self._oracle_addr_med} GOT MESSAGE params {params} and signature {signature}")

        # send message to all oracles to sign
        self.info(f"we {self._oracle_addr_med} GATHERING SIGNATURES:"
                  f"last pub blk {params.last_pub_block}, price: {params.price}")
        sigs = await gather_signatures(oracles, params, message, signature,
                                       timeout=self._conf.ORACLE_GATHER_SIGNATURE_TIMEOUT)
        if len(sigs) < len(oracles) // 2 + 1:
            self.error(f"we {self._oracle_addr_med} Publish: Not enough signatures")
            return False

        if settings.DEBUG:
            self.info(f"we {self._oracle_addr_med} GOT SIGS %r and params %r recover %r" %
                (sigs, params, [crypto.recover(hexstr=message, signature=x) for x in sigs]))

        self.info(f"we({self._oracle_addr_med}) publishing price: {params.price}")
        monitor.publish_log("%r : %r publishing price: %r" % (self._coin_pair, self._oracle_addr, params.price))
        try:
            self.info(f"we({self._oracle_addr_med}) SENDING TRANSACTION, "
                      f"last pub block {params.last_pub_block}, price {params.price}")
            tx = await self._cps.publish_price(params.version,
                                               params.coin_pair,
                                               params.price,
                                               params.oracle_addr,
                                               params.last_pub_block,
                                               sigs,
                                               account=oracle_settings.get_oracle_account(),
                                               wait=True,
                                               last_gas_price=await self.bs_loop.gas_calc.get_current())
            if is_error(tx):
                self.info(f"we{self._oracle_addr_med} ERROR PUBLISHING {repr(tx)}")
                return False
            self.info("//////////////////////////////////////////////////")
            self.info("//////////////////////////////////////////////////")
            self.info("//////////////////////////////////////////////////")
            self.info(f"we {self._oracle_addr_med} --------------------> PRICE PUBLISHED {repr(tx)}")
            self.info("//////////////////////////////////////////////////")
            self.info("//////////////////////////////////////////////////")
            self.info("//////////////////////////////////////////////////")
            # Last pub block has changed, force an update of the block chain info.
            await self.vi_loop.force_update()
            return True
        except asyncio.CancelledError as e:
            raise e
        except Exception as err:
            self.error(f"{self._oracle_addr_med} Publish: {repr(err)}")
            self.warning(traceback.format_exc())
            return False


async def gather_signatures(oracles, params: PublishPriceParams, message, my_signature, timeout=10):
    cors = [
        get_signature(oracle, params, message, my_signature, timeout=timeout)
        for oracle in oracles if oracle.addr != params.oracle_addr]
    # sigs = await asyncio.gather(*cors, return_exceptions=True)
    needed = len(oracles) // 2
    sigs = []
    for f in asyncio.as_completed(cors, timeout=timeout):
        sig = await f
        if sig is not None:
            sigs.append(sig)
        if len(sigs) >= needed:
            break
    sigs.append(OracleSignature(params.oracle_addr, my_signature))
    # Sort signatures by addr so the smart contract accept them.
    sorted_sigs = sorted([x for x in sigs if x is not None], key=lambda y: int(y.addr, 16))
    return [x.signature for x in sorted_sigs]


async def get_signature(oracle: FullOracleRoundInfo, params: PublishPriceParams, message, my_signature, timeout=10):
    x = urllib3.util.parse_url(oracle.internetName)
    target_uri = "%s://%s" % (x.scheme, x.host)
    if not x.port is None:
        target_uri+=':%d'%x.port
    target_uri += "/sign/"
    logger.info("%s : Trying to get signatures from: %s == %s" % (params.coin_pair, target_uri, oracle.addr), )
    try:
        post_data = {
            "version": str(params.version),
            "coin_pair": str(params.coin_pair),
            "price": str(params.price),
            "price_timestamp": str(params.price_ts_utc),
            "oracle_addr": params.oracle_addr,
            "last_pub_block": str(params.last_pub_block),
            "signature": my_signature.hex()}
        logger.debug(f"sign DATA {post_data}")
        logger.debug(f"sign target uri {target_uri}")

        raise_for_status = True
        if settings.DEBUG:
            raise_for_status = False
        response, status = await helpers.request_post(target_uri, post_data,
                                                      timeout=timeout,
                                                      raise_for_status=raise_for_status)
        if status != 200:
            logger.error(
                "%s : Signature rejected by %s, %s : %s" % (params.coin_pair, oracle.addr,
                                                            oracle.internetName, response))
            return
        obj = json.loads(response)
        if "signature" not in obj:
            logger.error(
                "%s : Missing signature from: %s, %s" % (params.coin_pair, oracle.addr, oracle.internetName))
            return
        signature = HexBytes(obj["signature"])
    except json.JSONDecodeError as err:
        logger.error(
            "%s : JSONDecodeError exception from %s, %s: %r for %r" % (
                params.coin_pair, oracle.addr, oracle.internetName, err,
                response if settings.DEBUG else "-"))
        logger.warning(traceback.format_exc())
        return
    except asyncio.CancelledError as e:
        raise e
    except asyncio.TimeoutError as e:
        logger.info("%s : Timeout from: %s, %s" % (params.coin_pair, oracle.addr, oracle.internetName))
        return
    except ClientResponseError as err:
        logger.info("%s : Invalid response from: %s, %s -> %r" % (
            params.coin_pair, oracle.addr, oracle.internetName, err.message))
        return
    except ClientConnectorError:
        logger.error("%s : Error connecting to: %s, %s" % (params.coin_pair, oracle.addr, oracle.internetName))
        return
    except InvalidURL:
        logger.error("%s : The oracle %s, %s is registered with a wrong url!!!" % (
            params.coin_pair, oracle.addr, oracle.internetName))
        return
    except Exception as err:
        logger.error(
            "%s : Unexpected exception from %s, %s: %r" % (
                params.coin_pair, oracle.addr, oracle.internetName, err))
        logger.warning(traceback.format_exc())
        return

    if not verify_signature(oracle.addr, message, signature):
        return

    # TODO: Verify that the oracle is still in the approved set (to avoid consuming gas later)
    logger.info("%s : Got valid signature from: %s, %s" % (params.coin_pair, oracle.addr, oracle.internetName))
    return OracleSignature(oracle.addr, signature)
