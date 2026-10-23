FROM debian:bookworm-slim AS patched-ca

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' ca-certificates)" ge '20250419~deb12u2' \
    && rm -rf /var/lib/apt/lists/*

FROM python:3.8

RUN rm -rf /etc/ssl/certs /usr/share/ca-certificates
COPY --from=patched-ca /usr/share/ca-certificates/ /usr/share/ca-certificates/
COPY --from=patched-ca /etc/ca-certificates.conf /etc/ca-certificates.conf
COPY --from=patched-ca /etc/ssl/certs/ /etc/ssl/certs/
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
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
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir 'certifi==2026.10.19'

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
