#!/bin/sh

# Create WireGuard keys if not present
if [ ! -f /etc/wireguard/privatekey ]; then
    echo "Generating WireGuard keys..."
    umask 077
    wg genkey | tee /etc/wireguard/privatekey | wg pubkey > /etc/wireguard/publickey
fi

WG_CONF="/etc/wireguard/wg0.conf"

if [ ! -f "$WG_CONF" ]; then
    echo "Creating default WireGuard config..."
    PRIVATE_KEY=$(cat /etc/wireguard/privatekey)
    cat > "$WG_CONF" <<EOF
[Interface]
Address = ${WG_DEFAULT_SUBNET:-10.128.0.0/9}
ListenPort = ${$WG_UDP_PORT:-1194}
PrivateKey = $PRIVATE_KEY
MTU = ${MTU:-1420}
PostUp = iptables -t nat -A POSTROUTING -s ${WG_DEFAULT_SUBNET:-10.128.0.0/9} -o eth0 -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -s ${WG_DEFAULT_SUBNET:-10.128.0.0/9} -o eth0 -j MASQUERADE
EOF
fi

echo "Creating folder for sqlite database..."
mkdir -p /home/db

echo "Starting WireGuard..."
wg-quick up wg0
chmod u+rw /etc/wireguard/wg0.conf
echo "Wireguard is up, starting the backend..."
uvicorn backend.main:app --host 0.0.0.0 --port ${WG_BACKEND_TCP_PORT:-8000} --log-level debug