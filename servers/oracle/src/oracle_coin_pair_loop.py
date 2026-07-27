from oracle.src.coin_pair_runner import CoinPairRunner
import os
from oracle.src.tasks_runner import TasksRunner
import urllib3
from urllib3.exceptions import LocationParseError
from aiohttp import ClientConnectorError, InvalidURL, ClientResponseError
from hexbytes import HexBytes

import asyncio
import json
import logging
import traceback
import typing
import time
from typing import Union

from common import crypto, settings, helpers
from common.bg_task_executor import BgTaskExecutor
from common.crypto import verify_signature
from common.helpers import MyCfgdLogger
from common.services.blockchain import is_error, BlockchainStateLoop, to_short
from common.services.conditional_publish import ConditionalPublishServiceBase
from oracle.src import monitor, oracle_settings
from oracle.src.oracle_coin_pair_service import FullOracleRoundInfo
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_publish_message import PublishPriceParams, PublishTaskParams

logger = logging.getLogger(__name__)

OracleSignature = typing.NamedTuple("OracleSignature",
                                    [("addr", str),
                                     ('signature', HexBytes)])

ETHER = 10**18


class OracleCoinPairLoop(BgTaskExecutor, MyCfgdLogger):
    def __init__(self, conf: OracleConfiguration,
                 runner: Union[CoinPairRunner, TasksRunner],
                 bs_loop: BlockchainStateLoop,
                 ):
        self.bs_loop = bs_loop
        self._conf = conf
        _acc = oracle_settings.get_oracle_account()
        self._oracle_addr = _acc.addr
        self._coin_pair = runner.cps.coin_pair
        self._runner = runner
        self._trace_enabled = bool(os.getenv("ORACLE_COINPAIR_TRACE"))
        super().__init__(name="OracleCoinPairLoop-%s" % self._coin_pair, main=self.run)
        self.reset(None, self._coin_pair, _acc.short)

    @property
    def signal(self) -> ConditionalPublishServiceBase:
        return self._runner.signal_service

    def trace(self, msg):
        if self._trace_enabled:
            logger.warning("%s TRACE %s", self._coin_pair, msg)

    async def run(self):
        self.debug("OracleCoinPairLoop start")
        self.trace(f"loop start oracle={self._oracle_addr}")
        await self.signal.update()

        round_info = await self._runner.cps.get_round_info()
        if is_error(round_info):
            self.error(f"ERROR getting round info {repr(round_info)}")
            self.trace("round info error")
            return self._conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL

        if round_info.round == 0:
            self.info(f"OCPL:Waiting for the initial round...")
            self.trace("round=0 waiting for initial round")
            return self._conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL

        blockchain_info = self._runner.vi_loop.get()
        if not blockchain_info:
            self.debug(f"waiting for blockchain info")
            self.trace("missing blockchain info")
            return self._conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL
        self.signal.from_blockchain(blockchain_info)

        is_available, my_turn, oracle_order = await self._runner.is_oracle_turn(
            blockchain_info, self._oracle_addr)
        self.trace(
            f"available={is_available} my_turn={my_turn} "
            f"blk={blockchain_info.block_num}/{blockchain_info.last_pub_block}"
        )
        if not is_available:
            return self._conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL

        fallback_index = None
        if my_turn and oracle_order:
            try:
                fallback_index = oracle_order.index(self._oracle_addr)
                # zero means is chosen, 1..x means fallback
            except ValueError:
                fallback_index = None
        
        oracle_order = ' '.join(to_short(addr) for addr in oracle_order)

        self.debug(f'prev hash: {blockchain_info.last_pub_block_hash.hex()}')
        msg = "Is  MY TURN" if my_turn else 'not my turn'
        self.info(f"---{self.signal}----> {msg} blk %r/%r  [{oracle_order}]  {self._runner.get_pre_publish_log(blockchain_info)}" %
                  (blockchain_info.block_num, blockchain_info.last_pub_block))
        if my_turn:
            self.trace(f"my turn fallback_index={fallback_index}")
            publish_success = await self.publish(blockchain_info.selected_oracles,
                                                 self._runner.prepare_publish_params(blockchain_info, self._oracle_addr),
                                                 fallback_index=fallback_index,
                                                 blockchain_info=blockchain_info)
            if not publish_success:
                self.trace("publish failed; retrying")
                # retry immediately.
                return 1
        return self._conf.ORACLE_COIN_PAIR_LOOP_TASK_INTERVAL

    async def publish(self, oracles, params: Union[PublishPriceParams, PublishTaskParams],
                      fallback_index=None, blockchain_info=None):
        str_as = ""
        if fallback_index is not None:
            # fallback_index, zero means is chosen, 1..x means fallback
            str_as = " AS CHOSEN" if fallback_index==0 else f" AS FALLBACK #{fallback_index}"
            str_as_low = " (chosen)" if fallback_index==0 else f" (fallback {fallback_index})"
        message = params.prepare_msg()
        signature = crypto.sign_message(hexstr="0x" + message, account=oracle_settings.get_oracle_account())
        self.info(f"GOT MESSAGE params {params} and signature {signature}")
        # send message to all oracles to sign
        self.info(f"GATHERING SIGNATURES:"
                  f"last pub blk {params.last_pub_block}, {params.log_data()}{str_as_low}")
        sigs = await gather_signatures(oracles, params, message, signature,
                                       timeout=self._conf.ORACLE_GATHER_SIGNATURE_TIMEOUT)
        if len(sigs) < len(oracles) // 2 + 1:
            self.info(f"Publish: Not enough signatures {len(sigs)}/{len(oracles)}{str_as_low}")
            self.trace(f"publish aborted: signatures {len(sigs)}/{len(oracles)}")
            return False
        else:
            self.info(f"Publish: enough signatures {len(sigs)}/{len(oracles)}{str_as_low}")

        if settings.DEBUG:
            self.debug(f"GOT SIGS %r and params %r recover %r" %
                ([to_short(x) for x in sigs], params,
                 [to_short(crypto.recover(hexstr=message, signature=x)) for x in sigs]))

        monitor.publish_log("%r : %r publishing: %r" % (self._coin_pair, self._oracle_addr, params.log_data()))
        try:
            str_block = f", block {blockchain_info.last_pub_block}" if blockchain_info else ""
            self.info(f"SENDING TRANSACTION{str_as}, last pub block {params.last_pub_block}, {params.log_data()}{str_block}")
            self.trace(f"sending tx {params.log_data()} {str_as_low}")
            tx = await self._runner.cps.publish(params,
                                               sigs,
                                               account=oracle_settings.get_oracle_account(),
                                               wait=True,
                                               last_gas_price=await self.bs_loop.gas_calc.get_current())
            if is_error(tx):
                self.error(f"ERROR PUBLISHING{str_as}, txid={repr(tx)}")
                self.trace(f"publish error: {repr(tx)}")
                return False
            self.info("//////////////////////////////////////////////////")
            self.info("//////////////////////////////////////////////////")
            self.info(f"PRICE PUBLISHED{str_as}, txid={repr(tx)}")
            self.info("//////////////////////////////////////////////////")
            self.info("//////////////////////////////////////////////////")
            self.trace(f"publish success {repr(tx)}")
            # Last pub block has changed, force an update of the blockchain info.
            await self._runner.vi_loop.force_update()
            return True
        except asyncio.CancelledError as e:
            raise e
        except Exception as err:
            self.error(f"Publish failed: {repr(err)}")
            self.warning(traceback.format_exc())
            self.trace(f"publish exception: {repr(err)}")
            return False


async def gather_signatures(oracles, params: Union[PublishPriceParams, PublishTaskParams], message, my_signature, timeout=10):

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


async def get_signature(oracle: FullOracleRoundInfo, params: Union[PublishPriceParams, PublishTaskParams],
                        message, my_signature, timeout=10):
    try:
        x = urllib3.util.parse_url(oracle.internetName)
    except (LocationParseError, ValueError, TypeError) as err:
        logger.error("%s : Invalid url for oracle %s, %s: %r" % (
            params.coin_pair, oracle.addr, oracle.internetName, err))
        return

    target_uri = "%s://%s" % (x.scheme, x.host)
    if x.port is not None:
        target_uri += ':%d' % x.port
    target_uri += params.get_post()
    logger.debug("%s : Trying to get signatures from: %s == %s" % (params.coin_pair, target_uri, oracle.addr))
    try:
        post_data = params.to_post_data(my_signature)
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
        if not isinstance(obj, dict):
            logger.error(
                "%s : Invalid signature payload from: %s, %s -> %r" % (
                    params.coin_pair, oracle.addr, oracle.internetName, obj))
            return
        if "signature" not in obj:
            logger.error(
                "%s : Missing signature from: %s, %s" % (params.coin_pair, oracle.addr, oracle.internetName))
            return
        signature_value = obj["signature"]
        if not isinstance(signature_value, (str, bytes, bytearray)):
            logger.error(
                "%s : Invalid signature type from: %s, %s -> %r" % (
                    params.coin_pair, oracle.addr, oracle.internetName, type(signature_value)))
            return
        signature = HexBytes(signature_value)
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

    try:
        if not verify_signature(oracle.addr, message, signature):
            logger.info(
                "%s : Signature verification failed for %s, %s" % (
                    params.coin_pair, oracle.addr, oracle.internetName))
            return
    except Exception as err:
        logger.error(
            "%s : Unexpected signature verification error for %s, %s: %r" % (
                params.coin_pair, oracle.addr, oracle.internetName, err))
        return

    # TODO: Verify that the oracle is still in the approved set (to avoid consuming gas later)
    logger.debug("%s : Got valid signature from: %s, %s" % (params.coin_pair, oracle.addr, oracle.internetName))
    return OracleSignature(oracle.addr, signature)
