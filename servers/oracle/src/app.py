import logging
import traceback
import socket
from urllib3 import util

from fastapi import Form, HTTPException, Response, status, Request

from common import settings, run_uvicorn
from common.services.oracle_dao import CoinPair, PriceWithTimestamp
from oracle.src.main_loop import MainLoop
from oracle.src.oracle_publish_message import PublishPriceParams
from oracle.src.request_validation import ValidationFailure


logger = logging.getLogger(__name__)
main_executor = MainLoop()
app = run_uvicorn.get_app("Oracle", "The moc reference oracle")


def getipaddresses(hostname):
    try:
        (hn, al, ipaddrlist) = socket.gethostbyname_ex(hostname)
        return ipaddrlist
    except socket.error:
        raise HTTPException(status_code=403, detail="Cannot resolve to a valid IP address")

@app.middleware("http")
async def filter_ips_by_selected_oracles(request: Request, call_next):
    (hostname, port) = request.client
    caller_ipaddrlist = getipaddresses(hostname)
    coin_pair_map = main_executor.oracle_loop.cpMap
    for cp_key in coin_pair_map:
        selected_oracles = coin_pair_map[cp_key].blockchain_info_loop.get().selected_oracles
        oracles_ipaddrlists = [getipaddresses(util.parse_url(oracle.internetName).host) for oracle in selected_oracles]
        for oracle_ipaddrlist in oracles_ipaddrlists:
            if any(ipaddr in caller_ipaddrlist for ipaddr in oracle_ipaddrlist):
                response = await call_next(request)
                return response
    raise HTTPException(status_code=403, detail="The request is not made by a selected oracle")


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
        print(version)
        print(coin_pair)
        print(price)
        print(price_timestamp)
        print(oracle_addr)
        print(last_pub_block)
        print(signature)
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
