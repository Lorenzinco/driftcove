FROM python:3-alpine

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apk add --no-cache \
    bash \
    ca-certificates \
    iproute2 \
    nftables \
    tcpdump \
    wireguard-tools && \
    mkdir -p /etc/wireguard

COPY ./requirements.txt /home/requirements.txt

RUN python3 -m pip install --no-cache-dir -r /home/requirements.txt
COPY . /home/backend
WORKDIR /home
RUN chmod +x /home/backend/init.sh

ENV PYTHONPATH=/home
CMD ["bash", "/home/backend/init.sh"]
