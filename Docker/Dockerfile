# ---------- build stage ----------
FROM debian:bookworm-slim AS base
FROM base as builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYENV_ROOT=/opt/pyenv
ENV PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git ca-certificates \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
    libsqlite3-dev libffi-dev liblzma-dev tk-dev xz-utils uuid-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/pyenv/pyenv.git $PYENV_ROOT

RUN pyenv install 3.12.13 && \
    pyenv install 3.8.20

RUN mkdir -p /app/omoc_node
RUN /opt/pyenv/versions/3.8.20/bin/python -m venv /app/omoc_node/.venv && \
    /app/omoc_node/.venv/bin/python -m pip install --upgrade pip setuptools wheel
COPY servers/requirements.txt .
RUN /app/omoc_node/.venv/bin/python -m pip install -r requirements.txt

RUN mkdir -p /app/moc_prices_source
RUN /opt/pyenv/versions/3.12.13/bin/python -m venv /app/moc_prices_source/.venv && \
    /app/moc_prices_source/.venv/bin/python -m pip install --upgrade pip setuptools wheel
RUN /app/moc_prices_source/.venv/bin/python -m pip install moneyonchain-prices-source==0.7.8

# ---------- runtime stage ----------
FROM base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    redis-server \
    supervisor \
    libssl3 zlib1g libbz2-1.0 libreadline8 libsqlite3-0 \
    libffi8 liblzma5 tk \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/pyenv/versions/3.12.13 /opt/pyenv/versions/3.12.13
COPY --from=builder /opt/pyenv/versions/3.8.20 /opt/pyenv/versions/3.8.20

COPY --from=builder /app/moc_prices_source/.venv /app/moc_prices_source/.venv
COPY --from=builder /app/omoc_node/.venv /app/omoc_node/.venv

WORKDIR /app/omoc_node
RUN mkdir -p /data
ENV LENDING_DB_PATH=/data/lending-index.sqlite3
VOLUME ["/data"]
COPY ./servers/build ./build
COPY ./servers/common ./common
COPY ./servers/oracle ./oracle
COPY ./servers/w3multicall ./w3multicall
COPY ./servers/exchanges.json ./exchanges.json
COPY ./Docker/files/env_file ./.env

WORKDIR /
RUN mkdir /root/.moc_prices_source
COPY ./Docker/files/redis.json /root/.moc_prices_source/
RUN mkdir -p /etc/supervisor/conf.d
COPY ./Docker/files/run.sh .
RUN chmod +x run.sh 

CMD [ "/bin/sh", "-c" , "/run.sh" ]
