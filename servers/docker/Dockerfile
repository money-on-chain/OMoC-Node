FROM debian:bookworm-slim AS patched-ca

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' ca-certificates)" ge '20250419~deb12u2' \
    && rm -rf /var/lib/apt/lists/*

FROM python:3.8
# uv 0.13.6; update this digest using https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /bin/uv

RUN rm -rf /etc/ssl/certs /usr/share/ca-certificates
COPY --from=patched-ca /usr/share/ca-certificates/ /usr/share/ca-certificates/
COPY --from=patched-ca /etc/ca-certificates.conf /etc/ca-certificates.conf
COPY --from=patched-ca /etc/ssl/certs/ /etc/ssl/certs/
ENV UV_SYSTEM_CERTS=true \
    UV_NO_MANAGED_PYTHON=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

RUN apt-get update && \
    apt-get install -y \
        locales

RUN echo $TZ > /etc/timezone && \
    apt-get update && apt-get install -y tzdata && \
    rm /etc/localtime && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean

COPY ./files/requirements.txt ./
RUN uv pip install --no-cache --python /usr/local/bin/python -r requirements.txt && \
    uv pip install --no-cache --python /usr/local/bin/python 'certifi==2026.10.19'

RUN mkdir /common
COPY ./files/common /common
RUN mkdir /oracle
COPY ./files/oracle /oracle
RUN mkdir /contracts
COPY ./files/contracts /contracts
COPY ./files/dotenv /.env
COPY ./files/run.sh /

WORKDIR /
ENV PATH "$PATH:/"
ENV PYTHONPATH "${PYTONPATH}:/"
CMD ["/run.sh"]
