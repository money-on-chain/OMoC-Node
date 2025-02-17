FROM python:3.8-alpine as base
FROM base as builder

RUN apk add build-base openssl-dev libffi-dev python3-dev py3-setuptools

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python3 -m pip install --upgrade pip
RUN pip install wheel
COPY servers/requirements.txt .

RUN pip install -r requirements.txt

FROM base

RUN apk add redis

COPY --from=builder /opt/venv /opt/venv

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /omoc-node

COPY ./servers/build ./build
COPY ./servers/common ./common
COPY ./servers/oracle ./oracle
COPY ./servers/w3multicall ./w3multicall

COPY ./servers/exchanges.json ./exchanges.json
COPY ./servers/requirements.txt ./requirements.txt 

COPY ./Docker/files/run.sh ./
COPY ./Docker/files/env_file ./.env

RUN mkdir /root/.moc_prices_source
COPY ./Docker/files/redis.json /root/.moc_prices_source/

RUN chmod +x run.sh 

CMD [ "/bin/sh", "-c" , "./run.sh" ]