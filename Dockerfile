FROM ubuntu:latest

ENV PYTHONUNBUFFERED=1

RUN apt update &&\
    apt install -y wireguard iproute2 iptables python3-pip &&\
    mkdir -p /etc/wireguard 

COPY backend/requirements.txt /home/requirements.txt

RUN pip3 install -r /home/requirements.txt --break-system-packages


COPY backend /home/backend
COPY assets/ /home/assets

WORKDIR /home

RUN chmod +x /home/backend/init.sh

CMD ["/home/backend/init.sh"]