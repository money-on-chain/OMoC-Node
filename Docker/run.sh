#!/bin/sh

echo ""
echo ""
echo "Start local Redis server..."
redis-server --save "" --appendonly no &
sleep 5

echo ""
echo ""
echo "Starts MoC prices source local API Rest webservice..."
moc_prices_source_api &
sleep 5

echo ""
echo ""
echo "Starts Decentralized oracle node..."
export TZ=UTC
export CONTRACT_ROOT_FOLDER=./
python -m oracle.src.main
