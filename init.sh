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
Address = ${WIREGUARD_SUBNET:-10.8.0.0/24}
ListenPort = $WIREGUARD_UDP_PORT
PrivateKey = $PRIVATE_KEY
PostUp = iptables -t nat -A POSTROUTING -s ${WIREGUARD_SUBNET:-10.8.0.0/24} -o eth0 -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -s ${WIREGUARD_SUBNET:-10.8.0.0/24} -o eth0 -j MASQUERADE
EOF
fi

echo "Starting WireGuard..."
wg-quick up wg0
chmod u+rw /etc/wireguard/wg0.conf
echo "Wireguard is up, starting the backend..."
uvicorn src.main:app --host 0.0.0.0 --port $WIREGUARD_API_BACKEND_PORT