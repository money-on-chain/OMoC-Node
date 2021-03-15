FROM python:3.7

RUN   apt-get update &&\
      apt-get -y upgrade &&\
      apt-get install -y software-properties-common curl locales &&\
      add-apt-repository ppa:deadsnakes/ppa &&\
      apt-get install -y python3-pip build-essential libssl-dev libffi-dev python3-dev vim python3-setuptools

RUN echo $TZ > /etc/timezone &&\
    apt-get install -y tzdata &&\
    rm /etc/localtime && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean

WORKDIR /omoc-node

COPY ./ ./

RUN mv ./Docker/oracle.sh . &&\
    chmod +x oracle.sh

RUN rm -rf ./Docker

RUN python3 -m pip install --upgrade pip &&\
    pip3 install --no-cache --upgrade pip setuptools wheel ethereum

RUN cd servers &&\
    pip3 install -r requirements.txt

ENV PATH "$PATH:/omoc-node"
ENV PYTHONPATH "${PYTHONPATH}:/omoc-node"
CMD [ "/bin/bash", "-c" , "./oracle.sh" ]