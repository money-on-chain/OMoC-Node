import types

import pytest

from oracle.src.ip_filter_loop import IpFilterLoop


class DummyOracleLoop:
    def __init__(self, blockchain_info):
        self._blockchain_info = blockchain_info

    async def get_full_blockchain_info(self):
        return self._blockchain_info


class DummyConf:
    ORACLE_BLOCKCHAIN_INFO_INTERVAL = 60


@pytest.mark.asyncio
async def test_ip_filter_loop_ignores_malformed_oracle_urls():
    blockchain_info = {
        "dummy": types.SimpleNamespace(
            selected_oracles=[
                types.SimpleNamespace(addr="0xabc", internetName="http://[")
            ]
        )
    }

    loop = IpFilterLoop(DummyOracleLoop(blockchain_info), DummyConf())

    result = await loop.run()

    assert result == 60
    assert loop.valid_ips == {}
