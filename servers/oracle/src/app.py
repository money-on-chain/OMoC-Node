import logging
import traceback

from fastapi import Form, HTTPException
from pydantic import BaseModel

from common import settings, run_uvicorn
from common.services.oracle_dao import CoinPair, PriceWithTimestamp
from oracle.src.main_loop import MainLoop
from oracle.src.oracle_publish_message import PublishPriceParams
from oracle.src.request_validation import ValidationFailure
from fastapi import Request


logger = logging.getLogger(__name__)
main_executor = MainLoop()
app = run_uvicorn.get_app("Oracle", "The moc reference oracle")


@app.middleware("http")
def filter_ips_by_selected_oracles(request: Request, call_next):
    (ip, port) = request.client
    caller_internet_name = ip + ":" + port
    body = request.json()
    oracle_loop = main_executor.oracle_loop
    blockchain_info_loop = oracle_loop.cpMap[body.coin_pair].blockchain_info_loop
    selected_oracles = blockchain_info_loop.get().selected_oracles
    internet_names = [oracle.internetName for oracle in selected_oracles]
    if caller_internet_name not in internet_names:
        #TODO shut off connection
        pass


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
        msg = str(e) if settings.DEBUG else "Invalid signature"
        raise HTTPException(status_code=500, detail=msg)
    except Exception as e:
        logger.error(e)
        if settings.ON_ERROR_PRINT_STACK_TRACE:
            logger.error("\n".join(traceback.format_exception(type(e), e, e.__traceback__)))
        msg = str(e) if settings.DEBUG else "Invalid signature"
        raise HTTPException(status_code=500, detail=msg)
