# ---------- build stage ----------
FROM debian:bookworm-slim AS base
FROM base as builder
# uv 0.13.6; update this digest using https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /bin/uv

ENV DEBIAN_FRONTEND=noninteractive
ENV PYENV_ROOT=/opt/pyenv
ENV PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
ENV UV_SYSTEM_CERTS=true
ENV UV_NO_MANAGED_PYTHON=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git ca-certificates \
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
    libsqlite3-dev libffi-dev liblzma-dev tk-dev xz-utils uuid-dev \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' ca-certificates)" ge '20250419~deb12u2' \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/pyenv/pyenv.git $PYENV_ROOT

RUN pyenv install 3.12.13 && \
    pyenv install 3.8.20

RUN mkdir -p /app/omoc_node
RUN uv venv --python /opt/pyenv/versions/3.8.20/bin/python /app/omoc_node/.venv && \
    uv pip install --python /app/omoc_node/.venv/bin/python \
    'setuptools==75.3.2' 'wheel==0.45.1'
COPY servers/requirements.txt .
RUN uv pip install --python /app/omoc_node/.venv/bin/python -r requirements.txt

RUN mkdir -p /app/moc_prices_source
RUN uv venv --python /opt/pyenv/versions/3.12.13/bin/python /app/moc_prices_source/.venv && \
    uv pip install --python /app/moc_prices_source/.venv/bin/python setuptools wheel
RUN uv pip install --python /app/moc_prices_source/.venv/bin/python moneyonchain-prices-source==0.7.10

# ---------- runtime stage ----------
FROM base

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    redis-server \
    supervisor \
    libssl3 zlib1g libbz2-1.0 libreadline8 libsqlite3-0 \
    libffi8 liblzma5 tk \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' ca-certificates)" ge '20250419~deb12u2' \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/pyenv/versions/3.12.13 /opt/pyenv/versions/3.12.13
COPY --from=builder /opt/pyenv/versions/3.8.20 /opt/pyenv/versions/3.8.20

COPY --from=builder /app/moc_prices_source/.venv /app/moc_prices_source/.venv
COPY --from=builder /app/omoc_node/.venv /app/omoc_node/.venv

WORKDIR /app/omoc_node
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
