FROM ubuntu:latest

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Base system + runtime dependencies
RUN apt update && \
    apt install -y --no-install-recommends \
    wireguard iproute2 nftables python3 python3-pip tcpdump ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /etc/wireguard

# Copy requirements separately for better caching
COPY ./requirements.txt /home/requirements.txt

# Install Python deps
RUN python3 -m pip install --no-cache-dir -r /home/requirements.txt --break-system-packages

COPY . /home/backend


WORKDIR /home

# Ensure init script is executable
RUN chmod +x /home/backend/init.sh

ENV PYTHONPATH=/home

CMD ["/home/backend/init.sh"]
