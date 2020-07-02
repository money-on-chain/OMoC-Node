import logging
import socket
import time
import typing

import urllib3

from common import helpers
from common.bg_task_executor import BgTaskExecutor
from oracle.src.oracle_configuration import OracleConfiguration
from oracle.src.oracle_loop import OracleLoop

logger = logging.getLogger(__name__)


class IpFilterLoop(BgTaskExecutor):

    def __init__(self, oracle_loop: OracleLoop, conf: OracleConfiguration):
        self.oracle_loop = oracle_loop
        self.conf = conf
        self.valid_ips: typing.Dict[str, float] = {}
        super().__init__(name="IpFilterLoop", main=self.run)

    async def run(self):
        logger.info("IpFilterLoop loop start")
        now = time.time()
        info = await self.oracle_loop.get_full_blockchain_info()
        print(info)
        # Populate the cache with new info
        for bi in info.values():
            for oracle in bi.selected_oracles:
                try:
                    name = urllib3.util.parse_url(oracle.internetName).host
                    for ip in helpers.get_ip_addresses(name):
                        self.valid_ips[ip] = now
                except socket.error as e:
                    logger.error("Cannot resolve %r to a valid IP address %r" % (name, e))
                    pass
        #  purge the cache
        for ip in self.valid_ips.keys():
            if now - self.valid_ips[ip] > self.conf.ORACLE_BLOCKCHAIN_INFO_INTERVAL * 2:
                del self.valid_ips[ip]
        return self.conf.ORACLE_BLOCKCHAIN_INFO_INTERVAL

    def is_valid_ip(self, ip):
        return ip in self.valid_ips
