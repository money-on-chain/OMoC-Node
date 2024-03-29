#
# NetSim.py
#
import asyncio
import logging
import os
import signal
import threading

import uvicorn
from starlette.datastructures import Secret

from common import settings, helpers
from common.ganache_accounts import GANACHE_ACCOUNTS
from common.services.blockchain import is_error, BlockchainAccount, parse_addr
from scripts import script_settings

logger = logging.getLogger(__name__)

accounts = [BlockchainAccount(x[0], Secret(x[1])) for x in GANACHE_ACCOUNTS]

oracleList = [
    {
        "name": "http://127.0.0.1:24000",
        "stake": (4 * 10 ** 18),
        "account": accounts[1],
        "owner": accounts[2],
    },
    {
        "name": "http://127.0.0.1:24002",
        "stake": (2 * 10 ** 18),
        "account": accounts[3],
        "owner": accounts[4],
    },
    {
        "name": "http://127.0.0.1:24004",
        "stake": (1 * 10 ** 18),
        "account": accounts[5],
        "owner": accounts[6]
    }
]

scheduler = "http://127.0.0.1:5555"


class MyServer(uvicorn.Server):
    def __init__(self, config, env):
        self.env = env
        super().__init__(config)

    def run(self, sockets=None):
        for k in self.env:
            os.environ[k] = self.env[k]
        self.config.setup_event_loop()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.serve(sockets=sockets))
        # $super().run(sockets)


# based o n uvicorn.subprocess.Multiprocess
class MyMultiprocess:
    def __init__(self):
        self.processes = []
        self.pid = os.getpid()
        self.should_exit = threading.Event()

    def signal_handler(self, sig, frame):
        self.should_exit.set()

    def startup(self):
        logger.info("Started parent process [{}]".format(str(self.pid)))
        for sig in uvicorn.supervisors.multiprocess.HANDLED_SIGNALS:
            signal.signal(sig, self.signal_handler)

    def run(self, config, target, sockets):
        process = uvicorn.subprocess.get_subprocess(config=config, target=target, sockets=sockets)
        process.start()
        self.processes.append(process)

    def shutdown(self):
        for process in self.processes:
            process.join()


async def register_oracles(oracle_manager_service, staking_machine_service, staking_machine_addr, moc_token_service, oe):
    info = await oracle_manager_service.get_oracle_registration_info(oe["owner"].addr)
    print("oracle_registration_info", info)
    if not is_error(info) and info.owner != "0x0000000000000000000000000000000000000000":
        if info.internetName != oe["name"]:
            tx = await staking_machine_service.set_oracle_name(oe["name"], account=oe["owner"],
                                                              wait=True)
            print("set name", tx)
        print("DONE", info)
        return True

    print("Registering oracle name=" + oe["name"] + " address=" + oe["account"].addr + " owner=" + oe["owner"].addr)
    tx = await staking_machine_service.register_oracle(
        oe["account"].addr,
        oe["name"],
        account=oe["owner"],
        wait=True
        )
    print("RegisterOracle TX:", tx)
    if is_error(tx):
        return False
    print("oracle %s already registered" % oe["account"].addr)
    tx = await moc_token_service.approve(
        staking_machine_addr,
        oe["stake"],
        account=oe["owner"],
        wait=True
        )
    print("Making deposit for owner=" + oe["owner"].addr + " with oracle address=" + oe["account"].addr)
    tx = await staking_machine_service.deposit(
        oe["stake"],
        oe["owner"].addr,
        account=oe["owner"],
        wait=True
        )
    print("Deposit TX:", tx)
    if is_error(tx):
        return False
    print("Deposit for oracle %s already made" % oe["account"].addr)

    return True


async def main():
    conf, oracle_service, oracle_manager_service, moc_token_service, staking_machine_service, staking_machine_addr = await script_settings.configure_oracle()
    print()
    print("MoC Oracle Network Simulator")
    print("=================================")
    print("Current settings: ")

    print("Scheduler @ " + scheduler)
    for oe in oracleList:
        print("Oracle name=" + oe["name"] + " address=" + oe["account"].addr)
        print("       balances: ETH=" +
              str(await script_settings.blockchain.get_balance(parse_addr(oe["account"].addr))) +
              "  MOC=" + str(await moc_token_service.balance_of(parse_addr(oe["account"].addr))))

    #  Register oracles.
    print("0. Mint tokens.")
    print("-----------------------------")
    for oe in oracleList:
        # tx = await moc_token_service.mint(oe["owner"].addr, oe["stake"], account=oe["owner"], wait=True)
        tx = await moc_token_service.transfer(oe["owner"].addr, oe["stake"],
                                              account=script_settings.SCRIPT_REWARD_BAG_ACCOUNT, wait=True)
        if is_error(tx):
            print("ERROR IN APPROVE", tx)
            return

    print("1. Oracle registration stage.")
    print("-----------------------------")
    registration = [await register_oracles(
        oracle_manager_service,
        staking_machine_service,
        staking_machine_addr,
        moc_token_service,
        oe) for oe in oracleList]
    if not all(registration):
        quit(1)

    print("1.5 Subscribe oracles.")
    print("-----------------------------")
    for coin_pair in script_settings.USE_COIN_PAIR:
        for oe in oracleList:
            tx = await staking_machine_service.subscribe_to_coin_pair(coin_pair, account=oe["owner"],
                                                                  wait=True)
            if is_error(tx):
                print("Already subscribed ", oe["account"].addr)
            else:
                print("Subscription TX:", tx)

    print("2. Start Oracle main loop")
    print("--------------------")

    supervisor = MyMultiprocess()
    supervisor.startup()
    for oe in oracleList:
        addr = oe["account"].addr
        port = int(oe["name"].split(":")[-1])
        logging_config = uvicorn.config.LOGGING_CONFIG.copy()
        logging_config["formatters"]["default"]["fmt"] = addr + " ---> %(asctime)s %(levelprefix)s %(message)s"
        logging_config["formatters"]["access"][
            "fmt"] = addr + ' ---> %(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
        config = uvicorn.Config("oracle.src.app:app", host="0.0.0.0",
                                port=port,
                                log_level="info",
                                reload=settings.RELOAD,
                                log_config=logging_config,
                                proxy_headers=settings.PROXY_HEADERS)
        server = MyServer(config, {"ORACLE_ADDR": addr, "ORACLE_PRIVATE_KEY": str(oe["account"].key)})
        supervisor.run(config, server.run, [config.bind_socket()])

    supervisor.shutdown()


if __name__ == '__main__':
    helpers.run_main(main)
