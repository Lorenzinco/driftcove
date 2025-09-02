FROM ubuntu:latest

ENV PYTHONUNBUFFERED=1

COPY backend /home/backend
COPY assets/ /home/assets

WORKDIR /home

RUN apt update &&\
    apt install -y wireguard iproute2 iptables python3-pip &&\
    mkdir -p /etc/wireguard &&\
    pip3 install -r /home/backend/requirements.txt --break-system-packages &&\
    chmod +x /home/backend/init.sh

CMD ["/home/backend/init.sh"]