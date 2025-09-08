#!/usr/bin/env bash
set -euo pipefail

# -------------------------
# Config (env-overridable)
# -------------------------
WG_IF="${WG_IF:-wg0}"
WG_CONF="/etc/wireguard/${WG_IF}.conf"
WG_UDP_PORT="${WG_UDP_PORT:-1194}"
WG_DEFAULT_SUBNET="${WG_DEFAULT_SUBNET:-10.128.0.0/9}"   # used for NAT saddr match
WG_ADDRESS_CIDR="${WG_ADDRESS_CIDR:-10.128.0.1/24}"      # Interface Address inside overlay
MTU="${MTU:-1420}"
WAN_IF="${WAN_IF:-eth0}"                                 # egress NIC for NAT
BACKEND_PORT="${WG_BACKEND_TCP_PORT:-8000}"

echo "[init] Driftcove init (Docker-mode)…"

# -------------------------
# WireGuard keys
# -------------------------
if [ ! -f /etc/wireguard/privatekey ]; then
  echo "[init] Generating WireGuard keys..."
  umask 077
  wg genkey | tee /etc/wireguard/privatekey | wg pubkey > /etc/wireguard/publickey
fi
PRIVATE_KEY="$(cat /etc/wireguard/privatekey)"

# -------------------------
# wg0.conf (create if missing)
# -------------------------
if [ ! -f "$WG_CONF" ]; then
  echo "[init] Creating default ${WG_IF} config at $WG_CONF"
  cat > "$WG_CONF" <<EOF
[Interface]
Address    = ${WG_ADDRESS_CIDR}
ListenPort = ${WG_UDP_PORT}
PrivateKey = ${PRIVATE_KEY}
MTU        = ${MTU}
# NAT and firewall handled by nftables below (no PostUp/Down here)
EOF
  chmod 600 "$WG_CONF"
fi

# -------------------------
# Kernel sysctls (Docker supplies via --sysctl / compose)
# -------------------------
# NOTE: Do NOT write /proc/sys here; containers often have read-only sysctl.
echo "[init] Skipping sysctl writes; set these in Docker/compose:"
echo "       - net.ipv4.ip_forward=1"
echo "       - net.ipv4.conf.all.rp_filter=0 (and default / ${WG_IF} as needed)"

# -------------------------
# nftables scaffold (inet dcv + ip nat)
# -------------------------
echo "[init] Bootstrapping nftables (inet dcv + ip nat)"

# Table + sets (idempotent)
nft list table inet dcv >/dev/null 2>&1 || nft add table inet dcv
nft 'add set inet dcv p2p_links { type ipv4_addr . ipv4_addr; flags interval; }' 2>/dev/null || true
nft 'add set inet dcv svc_guest { type ipv4_addr . ipv4_addr . inet_service; flags interval; }' 2>/dev/null || true
nft 'add set inet dcv admin_links { type ipv4_addr . ipv4_addr; flags interval; }' 2>/dev/null || true
nft 'add set inet dcv admin_peer2cidr { type ipv4_addr . ipv4_addr; flags interval; }' 2>/dev/null || true

# Chains (idempotent)
nft 'add chain inet dcv forward { type filter hook forward priority 0; policy accept; }' 2>/dev/null || true
nft 'add chain inet dcv wg' 2>/dev/null || true          # regular chain (no policy!)
nft 'add chain inet dcv wg_base' 2>/dev/null || true     # static allows
nft 'add chain inet dcv wg_allow' 2>/dev/null || true    # dynamic allows

# Replies fast-path (ensure once)
nft 'insert rule inet dcv forward ct state established,related accept' 2>/dev/null || true

# Hook only WG traffic into wg
nft "insert rule inet dcv forward iifname \"${WG_IF}\" goto wg" 2>/dev/null || true
nft "insert rule inet dcv forward oifname \"${WG_IF}\" goto wg" 2>/dev/null || true

# wg dispatch: base -> allow -> reject (ensure once)
nft 'add rule inet dcv wg jump wg_base' 2>/dev/null || true
nft 'add rule inet dcv wg jump wg_allow' 2>/dev/null || true
nft 'add rule inet dcv wg counter reject with icmpx type admin-prohibited' 2>/dev/null || true

# Seed base rules once (Python will normalize on startup too)
nft 'add rule inet dcv wg_base ip saddr . ip daddr @admin_peer2cidr ct state new accept' 2>/dev/null || true
nft 'add rule inet dcv wg_base ip saddr . ip daddr @admin_links   ct state new accept' 2>/dev/null || true
nft 'add rule inet dcv wg_base ip saddr . ip daddr @p2p_links     ct state new accept' 2>/dev/null || true
nft 'add rule inet dcv wg_base meta l4proto { tcp, udp } ip saddr . ip daddr . th dport @svc_guest ct state new accept' 2>/dev/null || true

# NAT table: masquerade WG subnet out of WAN_IF
nft list table ip nat >/dev/null 2>&1 || nft add table ip nat
nft 'add chain ip nat prerouting  { type nat hook prerouting  priority -100; }' 2>/dev/null || true
nft 'add chain ip nat postrouting { type nat hook postrouting priority  100; }' 2>/dev/null || true
# Refresh masquerade rule idempotently
nft "delete rule ip nat postrouting oifname \"${WAN_IF}\" ip saddr ${WG_DEFAULT_SUBNET} counter masquerade" 2>/dev/null || true
nft "add rule ip nat postrouting oifname \"${WAN_IF}\" ip saddr ${WG_DEFAULT_SUBNET} counter masquerade"

echo "[init] Ensuring sqlite db folder..."
mkdir -p /home/db

# -------------------------
# Bring up WireGuard and start backend
# -------------------------
echo "[init] Starting WireGuard (${WG_IF})..."
wg-quick up "${WG_IF}" || (echo "[init] wg-quick up failed" && exit 1)
chmod u+rw "$WG_CONF"

echo "[init] WireGuard up. Starting backend on ${BACKEND_PORT}…"
exec uvicorn backend.main:app --host 0.0.0.0 --port "${BACKEND_PORT}"