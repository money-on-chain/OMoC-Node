FROM alpine:latest

RUN apk add --update npm &&\
    apk add --update --no-cache nodejs npm \
                    alpine-sdk \
                    bash 

RUN npm install -g pm2 &&\
    pm2 install pm2-logrotate

ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3 && ln -sf python3 /usr/bin/python &&\
    apk add --update python3-dev libffi-dev openssl openssl-dev

WORKDIR /omoc-node

COPY ./ ./
RUN mv ./Docker/oracle.sh . &&\
    chmod +x oracle.sh
RUN rm -r ./Docker

RUN python3 -m ensurepip &&\
    python3 -m pip install --upgrade pip &&\
    pip3 install virtualenv &&\
    pip3 install --no-cache --upgrade setuptools &&\
    pip3 install wheel && \
    pip3 install ethereum


RUN cd scripts &&\
    pip3 install -r requirements.txt

RUN cd servers &&\
    pip3 install -r requirements.txt


# Opt2 to do and develop --> how to activate virtual envs from inside bash scripts
#RUN cd scripts &&\
#    python3 -m venv env &&\
#    source env/bin/activate &&\
#    python3 -m pip install --upgrade pip &&\
#    pip3 install --no-cache --upgrade setuptools wheel ethereum &&\
#    pip3 install -r requirements.txt &&\ 
#    deactivate

#RUN cd servers &&\
#    python3 -m venv env &&\
#    source env/bin/activate &&\
#    python3 -m pip install --upgrade pip &&\
#    pip3 install --no-cache --upgrade setuptools wheel &&\
#    pip3 install -r requirements.txt 

EXPOSE 5556

CMD [ "/bin/bash", "-c" , "./oracle.sh" ]