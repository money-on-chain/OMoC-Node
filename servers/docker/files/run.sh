#!/bin/bash

check_env () {
  if test -z "${!1}" ; then
    if test -z "$2" ; then
      echo "Environment $1 is empty" 1>&2
      exit 1
    else
      echo Using environment $2 as $1
      export "$1"="${!2}"
    fi
  fi
}

check_env NODE_URL
check_env CHAIN_ID
check_end ORACLE_PORT
check_env ORACLE_ADDR
check_env ORACLE_PRIVATE_KEY
check_env REGISTRY_ADDR

export TZ=UTC

python -m oracle.src.main
