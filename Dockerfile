FROM ubuntu:latest

ENV PYTHONUNBUFFERED=1

COPY ./init.sh /home/init.sh
COPY app/ /home/app
COPY assets/ /home/assets

WORKDIR /home

RUN apt update &&\
    apt install -y wireguard iproute2 iptables python3-pip &&\
    mkdir -p /etc/wireguard &&\
    pip3 install -r /home/app/requirements.txt --break-system-packages &&\
    chmod +x /home/init.sh

CMD ["/home/init.sh"]