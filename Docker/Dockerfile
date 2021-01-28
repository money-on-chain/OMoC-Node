FROM ubuntu:latest

RUN   apt-get update && apt-get -y upgrade &&\
      apt-get install -y software-properties-common curl &&\
      add-apt-repository ppa:deadsnakes/ppa &&\
      apt-get install -y python3-pip build-essential libssl-dev libffi-dev python3-dev vim python3-setuptools

RUN echo $TZ > /etc/timezone && \
    apt-get update && apt-get install -y tzdata && \
    rm /etc/localtime && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean

RUN cd ~ &&\
    curl -sL https://deb.nodesource.com/setup_12.x -o nodesource_setup.sh &&\
    bash nodesource_setup.sh &&\
    apt install -y nodejs

RUN npm install -g pm2 &&\
    pm2 install pm2-logrotate &&\
    cd

WORKDIR /omoc-node

COPY ./ ./

RUN mv ./Docker/oracle.sh . &&\
    chmod +x oracle.sh
RUN rm -r ./Docker

RUN python3 -m pip install --upgrade pip &&\
    pip3 install --no-cache --upgrade pip setuptools wheel ethereum


RUN cd scripts &&\
    pip3 install -r requirements.txt

RUN cd servers &&\
    pip3 install -r requirements.txt

EXPOSE 5556

CMD [ "/bin/bash", "-c" , "./oracle.sh" ]