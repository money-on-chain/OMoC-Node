import logging
import traceback

from fastapi import Form, HTTPException, Response, Request
from starlette.responses import JSONResponse

from common import settings, run_uvicorn
from common.helpers import dt_now_at_utc
from common.services.blockchain import BlockChain
from common.services.coin_pair_price_service import CoinPairService
from common.services.oracle_dao import CoinPair, PriceWithTimestamp
from oracle.src import oracle_settings
from oracle.src.main_loop import MainLoop
from oracle.src.oracle_blockchain_info_loop import OracleBlockchainInfoLoop
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_publish_message import PublishPriceParams
from oracle.src.oracle_settings import ORACLE_PRICE_ENGINES_SIG
from oracle.src.request_validation import ValidationFailure

logger = logging.getLogger(__name__)
main_executor = MainLoop()
app = run_uvicorn.get_app("Oracle", "The moc reference oracle")

not_authorized_msg = "The request was not made by a selected oracle."

# endpoints which can be accessed by anyone
OPEN_ENDPOINTS = {'/version', '/info'}


def get_error_msg(msg=None):
    return str(msg) if msg is not None else "Can't be signed"


@app.middleware("http")
async def filter_ips_by_selected_oracles(request: Request, call_next):
    logger.debug(f"ORACLE_RUN_IP_FILTER: {oracle_settings.ORACLE_RUN_IP_FILTER}")
    if not oracle_settings.ORACLE_RUN_IP_FILTER:
        return await call_next(request)
    try:
        (ip, port) = request.client
        logger.info("Got a connection to %s from %r" % (request.url.path, ip))
        if not (request.url.path in OPEN_ENDPOINTS):
            if not main_executor.is_valid_ip(ip):
                raise Exception("%s %r" % (not_authorized_msg, ip))
        return await call_next(request)
    except Exception as e:
        error_msg = get_error_msg(e.args[0]) if len(e.args) else get_error_msg(
                                  e)
        logger.error(error_msg)
        if settings.DEBUG:
            return JSONResponse(status_code=418, content=error_msg)
        return Response(status_code=417, content=error_msg)


@app.on_event("startup")
async def startup():
    await main_executor.web_server_startup()


@app.on_event("shutdown")
def shutdown_event():
    main_executor.shutdown()


@app.get("/")
async def read_root():
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/version")
async def read_version():
    return {'version': settings.VERSION}


@app.get("/info")
async def read_info():
    def fill_blockchain_info(bc: BlockChain):
        bkc_data = {}
        if not(bc.latest_block is None):
            block = bc.latest_block
            bkc_data['block_at'] = bc.latest_block_at
            bkc_data['block_nr'] = block.number
            bkc_data['block_hash'] = block['hash'].hex()
        return bkc_data

    def fill_cp_info(cps: CoinPairService):
        return {'our_last_pub_at': cps.last_pub_at}

    data = {
        'version': settings.VERSION,
        'ts': dt_now_at_utc(),
        'config_hash': ORACLE_PRICE_ENGINES_SIG,
        'cfg:': {
            'ORACLE_ENTERING_FALLBACKS_MULTIPLIER':
                OracleConfiguration.instance.ORACLE_ENTERING_FALLBACKS_MULTIPLIER,
        }
    }
    try:
        bkc = main_executor.cf.get_blockchain()
        data.update(fill_blockchain_info(bkc))
        cpm = main_executor.oracle_loop.cpMap
        data['coinpairs'] = list(cpm.keys())
        for cp in cpm.keys():
            obl: OracleBlockchainInfoLoop = cpm[cp].blockchain_info_loop
            data[cp] = {'last_pub_block': obl._blockchain_info.last_pub_block}
            data[cp].update(fill_cp_info(obl._cps._coin_pair_service))
    except Exception as err:
        data['error'] = str(err)
    return data


@app.post("/sign/")
async def sign(*, version: str = Form(...),
               coin_pair: str = Form(...),
               price: str = Form(...),
               price_timestamp: str = Form(...),
               oracle_addr: str = Form(...),
               last_pub_block: str = Form(...),
               signature: str = Form(...)):
    try:
        params = PublishPriceParams(int(version), CoinPair(coin_pair),
                                    PriceWithTimestamp(int(price),
                                                       float(price_timestamp)),
                                    oracle_addr,
                                    int(last_pub_block))

        validation_data = await main_executor.get_validation_data(params)
        if not validation_data:
            raise ValidationFailure("Missing coin pair", coin_pair)

        logger.debug("Before")
        logger.debug("Sign: %r" % (params,))
        message, my_signature = validation_data.validate_and_sign(signature)
        logger.debug(f"Sign After: {message} {my_signature}")
        return {
            "message": message,
            "signature": my_signature.hex()
        }

    except ValidationFailure as e:
        logger.warning(e)
        raise HTTPException(status_code=424, detail=get_error_msg(e))
    except Exception as e:
        logger.error(e)
        if settings.ON_ERROR_PRINT_STACK_TRACE:
            logger.error("\n".join(
                traceback.format_exception(type(e), e, e.__traceback__)))
        raise HTTPException(status_code=422, detail=get_error_msg(e))
