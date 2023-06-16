FROM python:3.7-alpine as base
FROM base as builder

RUN apk add build-base openssl-dev libffi-dev  python3-dev 	py3-setuptools

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python3 -m pip install --upgrade pip
RUN pip install wheel
COPY servers/requirements.txt .

RUN pip install -r requirements.txt

FROM base
COPY --from=builder /opt/venv /opt/venv

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /omoc-node

COPY ./servers ./
COPY ./Docker/run.sh ./

RUN chmod +x run.sh 

CMD [ "/bin/sh", "-c" , "./run.sh" ]