FROM ubuntu:latest

COPY ./init.sh /init.sh
COPY src/ /src

RUN apt update &&\
    apt install -y wireguard iproute2 iptables python3-pip &&\
    mkdir -p /etc/wireguard &&\
    pip3 install -r /src/requirements.txt --break-system-packages &&\
    chmod +x /init.sh

CMD ["/init.sh"]