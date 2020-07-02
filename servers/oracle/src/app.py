import logging
import traceback

from fastapi import Form, HTTPException, Response, Request

from common import settings, run_uvicorn
from common.services.oracle_dao import CoinPair, PriceWithTimestamp
from oracle.src import oracle_settings
from oracle.src.main_loop import MainLoop
from oracle.src.oracle_publish_message import PublishPriceParams
from oracle.src.request_validation import ValidationFailure

logger = logging.getLogger(__name__)
main_executor = MainLoop()
app = run_uvicorn.get_app("Oracle", "The moc reference oracle")

not_authorized_msg = "The request was not made by a selected oracle."


def get_error_msg(msg=None):
    return str(msg) if msg is not None and settings.DEBUG else "Invalid signature"


@app.middleware("http")
async def filter_ips_by_selected_oracles(request: Request, call_next):
    if not oracle_settings.ORACLE_RUN_IP_FILTER:
        return await call_next(request)
    try:
        (ip, port) = request.client
        logger.info("Got a connection from %r" % ip)
        if not main_executor.is_valid_ip(ip):
            raise Exception("%s %r" % (not_authorized_msg, ip))
        return await call_next(request)
    except Exception as e:
        error_msg = get_error_msg(e.args[0]) if len(e.args) else get_error_msg(e)
        logger.error(error_msg)
        return Response(status_code=500, content=error_msg)


@app.on_event("startup")
async def startup():
    await main_executor.web_server_startup()


@app.on_event("shutdown")
def shutdown_event():
    main_executor.shutdown()


@app.get("/")
async def read_root():
    raise HTTPException(status_code=404, detail="Item not found")


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

        logger.debug("Sign: %r" % (params,))
        message, my_signature = validation_data.validate_and_sign(signature)
        return {
            "message": message,
            "signature": my_signature.hex()
        }

    except ValidationFailure as e:
        logger.warning(e)
        raise HTTPException(status_code=500, detail=get_error_msg(e))
    except Exception as e:
        logger.error(e)
        if settings.ON_ERROR_PRINT_STACK_TRACE:
            logger.error("\n".join(traceback.format_exception(type(e), e, e.__traceback__)))
        raise HTTPException(status_code=500, detail=get_error_msg(e))
