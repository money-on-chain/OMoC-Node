# LiquidationEngine node integration

The node treats the OMOC `LiquidationEngine` as an independent service named
`LENDING`. Legacy tasks remain exclusively in `TasksRunner`; lending
liquidations are discovered locally and submitted to `runLiquidations`.

This integration targets contract commit
`5da4692edd5b2c1bb48afed644d25e4174bbf9fb`.

## Authorization and execution

The contract accepts liquidations grouped by registered lending pool:

```solidity
struct PoolLiquidations {
    bytes32 poolId;
    address[] users;
}
```

The publisher and peers sign the contract's 116-byte authorization:

```text
message = version || name || votedOracle || lastPublicationBlock
```

The liquidation batch is deliberately not sent to `/sign-liquidation/` because
it is not part of the contract's signed message. Peers validate only the
publisher authorization: version, service name, oracle turn, signature and
`lastPublicationBlock`. The publisher checks pools and queries
`LendingManager.isLiquidationAvailable(user, tpToken, mocBucket)` locally before
submitting the selected batch to `runLiquidations`.

`LiquidationEngine` has its own registration, round and
`lastPublicationBlock`, independent from `TasksRunner`. It therefore appears as
a separate entry in `ORACLE_COIN_PAIR_FILTER`, normally `LENDING`.

## Local lending indexer

Each node discovers candidates independently. A background task scans the
configured Lending Manager for
`VaultStateUpdated(address,address,address,uint256,uint256,bool)` logs through
its own RPC. Absolute vault state, processed events, retained block hashes and
the projection cursor are stored in a local SQLite database using WAL mode.

The scanner advances only to `chainHead - LENDING_CONFIRMATIONS`. Before each
range it verifies the cursor block hash. A mismatch rolls events back to the
latest retained canonical checkpoint; if no checkpoint survives, only the
lending database is reset and backfilled from the deployment block.

Candidate risk is ordered with exact Python integers: partial liquidations
first, then zero-collateral debt, then `creditUnits / acBalance` descending,
with user address ascending as tie breaker. The index is discovery only;
on-chain simulation is the final preflight check.

## Configuration

```dotenv
ORACLE_COIN_PAIR_FILTER='["BTCUSD","TASKS","LENDING"]'
LIQUIDATION_MESSAGE_VERSION=3
LIQUIDATION_ENGINE_GAS_LIMIT=0
MULTICALL_ADDR="0x..."

LENDING_INDEXER_ENABLED=true
LENDING_MANAGER_ADDRESS="0x..."
LENDING_DEPLOYMENT_BLOCK=123456
LENDING_DB_PATH="/data/lending-index.sqlite3"
LENDING_CONFIRMATIONS=2
LENDING_GET_LOGS_BLOCK_RANGE=2000
LENDING_INDEX_INTERVAL=10
LENDING_DISCOVERY_TIMEOUT=2
LENDING_MAX_LAG_BLOCKS=20
LENDING_REORG_RETENTION_BLOCKS=1000
LENDING_LIQUIDATION_MARKETS='[{"tpToken":"0x...","mocBucket":"0x..."}]'
```

The SQLite path must point to a persistent container volume. An indexer error
or excessive lag disables local proposals but does not affect price publication
or legacy TasksRunner execution. The Docker image defaults `LENDING_DB_PATH` to
`/data/lending-index.sqlite3`; deployments must attach a named volume or bind
mount to `/data` so the index survives container replacement.

The publisher reads `maxLiquidationsPerBatch` from `LiquidationEngine` before
each discovery and never builds a transaction with more attempts than the
current on-chain limit. The limit counts attempted liquidations globally across
all pools, including repeated users and failed attempts.

Candidates are interleaved by risk rank across markets until the on-chain limit
is reached: the riskiest vault from every market, then the second riskiest, and
so on. The publisher checks that single candidate batch through
`Multicall.tryAggregate(false, calls)` using `isLiquidationAvailable`; unavailable
positions are omitted without refilling their slots. If the configured Multicall
is unavailable or does not support `tryAggregate`, the node falls back to
individual `eth_call` requests.

Discovery has a total wait budget of `LENDING_DISCOVERY_TIMEOUT` seconds. At
most one discovery operation remains in flight per LiquidationRunner. A failure
backs off for `LENDING_INDEX_INTERVAL`.

For an operator-driven resync, stop the node, move the SQLite file and its
`-wal`/`-shm` companions to a backup location, and restart. The new database
backfills from `LENDING_DEPLOYMENT_BLOCK`.

## Process isolation

The runner is logically independent inside the node. Running `LENDING` in a
different OS process with the same oracle private key still requires an external
transaction dispatcher or distributed nonce coordination; the in-memory nonce
manager only serializes transactions inside one process.
