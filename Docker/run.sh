#!/bin/sh
cd servers
export TZ=UTC
export CONTRACT_ROOT_FOLDER=../contracts
python -m oracle.src.main