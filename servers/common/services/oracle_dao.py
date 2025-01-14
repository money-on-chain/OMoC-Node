import logging
import typing
from typing import List
import collections
from datetime import datetime

from common.services.blockchain import BlockChainAddress

logger = logging.getLogger(__name__)


class CoinPair:
    def __init__(self, cp):
        self.cp = self.shorter(cp)

    def longer(self):
        return self.cp.encode("ascii").ljust(32, b'\0')

    @staticmethod
    def shorter(cp):
        while cp[-1] == "\x00":
            cp = cp[:-1]
        return cp

    def __str__(self):
        return self.cp

    def __repr__(self):
        return self.__str__()


PriceWithTimestamp = typing.NamedTuple('PriceWithTimestamp', [('price', int), ('ts_utc', int)])

CoinPairInfo = typing.NamedTuple("CoinPairInfo",
                                 [("coin_pair", CoinPair),
                                  ('addr', BlockChainAddress)])

OracleRegistrationInfo = typing.NamedTuple("OracleRegistrationInfo",
                                           [("addr", str),
                                            ('internetName', str),
                                            ("stake", int),
                                            ("owner", str)])

OracleRoundInfo = typing.NamedTuple("OracleRoundInfo",
                                    [("points", int),
                                     ("selectedInCurrentRound", bool),
                                     ("selectedInRound", int)
                                     ])


#class RoundInfo(collections.namedtuple("RoundInfo", [('round', int),
#                                            ("startBlock", int),
#                                            ("lockPeriodTimestamp", int),
#                                            ("totalPoints", int),
#                                            ("selectedOwners", List[str]),
#                                            ("selectedOracles", List[str])])):
class RoundInfo(collections.namedtuple("RoundInfo", ['round',
                                            "startBlock",
                                            "lockPeriodTimestamp",
                                            "totalPoints",
                                            "selectedOwners",
                                            "selectedOracles"])):
    def __repr__(self):
        lock = datetime.fromtimestamp(self.lockPeriodTimestamp)
        lock = lock.time()
        #return f"RoundInfo(round={self.round}, startBlock={self.startBlock}, lockPeriodTimestamp={lock}, totalPoints={self.totalPoints}, selectedOwners={self.selectedOwners}, selectedOracles={self.selectedOracles})"
        selectedOracles = '[%s]'% (', '.join(['%s'%(oracle[:6]+'..'+oracle[-2:]) for oracle in self.selectedOracles]))
        return f"RoundInfo(rnd={self.round}, startBlk={self.startBlock}, lockPeriod={lock}, selectedOracles={selectedOracles})"


FullOracleRoundInfo = typing.NamedTuple("FullOracleRoundInfo",
                                        [("addr", str),
                                         ('internetName', str),
                                         ("stake", int),
                                         ("owner", str),
                                         ("points", int),
                                         ("selectedInCurrentRound", bool),
                                         ("selectedInRound", int)
                                         ])

OracleBlockchainInfo = typing.NamedTuple("OracleBlockchainInfo",
                                         [("coin_pair", CoinPair),
                                          ('selected_oracles', typing.List[FullOracleRoundInfo]),
                                          ('blockchain_price', int),
                                          ('block_num', int),
                                          ('last_pub_block', int),
                                          ('last_pub_block_hash', str),
                                          ('valid_price_period_in_blocks', int)
                                          ])
