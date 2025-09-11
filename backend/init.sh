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

# Core sets
nft 'add set inet dcv p2p_links       { type ipv4_addr . ipv4_addr; flags interval; }' 2>/dev/null || true
nft 'add set inet dcv svc_guest       { type ipv4_addr . ipv4_addr . inet_service; flags interval; }' 2>/dev/null || true
# Pair-only set used to accept ESTABLISHED service flows (port was checked at NEW)
nft 'add set inet dcv svc_pairs       { type ipv4_addr . ipv4_addr; flags interval; }' 2>/dev/null || true
nft 'add set inet dcv admin_links     { type ipv4_addr . ipv4_addr; flags interval; }' 2>/dev/null || true
nft 'add set inet dcv admin_peer2cidr { type ipv4_addr . ipv4_addr; flags interval; }' 2>/dev/null || true
# Panic drop set (no timeout/dynamic for container kernels)
nft 'add set inet dcv blocked_pairs   { type ipv4_addr . ipv4_addr; flags interval; }' 2>/dev/null || true

# Chains (idempotent)
nft 'add chain inet dcv input   { type filter hook input   priority 0; policy accept; }' 2>/dev/null || true
nft 'add chain inet dcv forward { type filter hook forward priority 0; policy accept; }' 2>/dev/null || true
nft 'add chain inet dcv fwd_est'   2>/dev/null || true   # <-- NEW: holds EST/REL rules
nft 'add chain inet dcv wg'        2>/dev/null || true
nft 'add chain inet dcv wg_base'   2>/dev/null || true
nft 'add chain inet dcv wg_allow'  2>/dev/null || true

# --- INPUT (to the server on wg0) ---
nft 'flush chain inet dcv input' 2>/dev/null || true
# Replies fast-path
nft 'add rule inet dcv input ct state established,related accept' 2>/dev/null || true
# Allow ping to the server tunnel IP
nft "add rule inet dcv input iifname \"${WG_IF}\" ip daddr ${WG_ADDRESS_CIDR%%/*} icmp type echo-request accept" 2>/dev/null || true
# (optional) SSH on wg interface:
# nft "add rule inet dcv input iifname \"${WG_IF}\" ip daddr ${WG_ADDRESS_CIDR%%/*} tcp dport 22 accept" 2>/dev/null || true

# --- FORWARD (static: drop -> jump fwd_est -> goto wg) ---
nft 'flush chain inet dcv forward' 2>/dev/null || true

# 0) Immediate hard drop for blocked pairs (cuts live regardless of conntrack)
nft 'add rule inet dcv forward ip saddr . ip daddr @blocked_pairs drop' 2>/dev/null || true

# 1) Constrained EST/REL lives in fwd_est (jump there)
nft 'add rule inet dcv forward jump fwd_est' 2>/dev/null || true

# 2) Hook only WG traffic into wg chain (leave these LAST)
nft "add rule inet dcv forward iifname \"${WG_IF}\" goto wg" 2>/dev/null || true
nft "add rule inet dcv forward oifname \"${WG_IF}\" goto wg" 2>/dev/null || true

# --- FWD_EST: constrained EST/REL acceptance by original tuple ---
nft 'flush chain inet dcv fwd_est' 2>/dev/null || true
nft 'add rule inet dcv fwd_est ct state established,related ct original ip saddr . ct original ip daddr @admin_peer2cidr accept' 2>/dev/null || true
nft 'add rule inet dcv fwd_est ct state established,related ct original ip saddr . ct original ip daddr @admin_links     accept' 2>/dev/null || true
nft 'add rule inet dcv fwd_est ct state established,related ct original ip saddr . ct original ip daddr @p2p_links       accept' 2>/dev/null || true
# For services: accept established by src/dst pair (port was enforced at NEW via svc_guest)
nft 'add rule inet dcv fwd_est ct state established,related ct original ip saddr . ct original ip daddr @svc_pairs       accept' 2>/dev/null || true

# --- wg dispatch: base -> allow -> drop ---
nft 'flush chain inet dcv wg' 2>/dev/null || true
nft 'add rule inet dcv wg jump wg_base' 2>/dev/null || true
nft 'add rule inet dcv wg jump wg_allow' 2>/dev/null || true
nft 'add rule inet dcv wg counter drop' 2>/dev/null || true

# --- wg_base: NEW accepts from sets ---
nft 'flush chain inet dcv wg_base' 2>/dev/null || true
nft 'add rule inet dcv wg_base ip saddr . ip daddr @admin_peer2cidr ct state new accept' 2>/dev/null || true
nft 'add rule inet dcv wg_base ip saddr . ip daddr @admin_links   ct state new accept' 2>/dev/null || true
nft 'add rule inet dcv wg_base ip saddr . ip daddr @p2p_links     ct state new accept' 2>/dev/null || true
nft 'add rule inet dcv wg_base meta l4proto { tcp, udp } ip saddr . ip daddr . th dport @svc_guest ct state new accept' 2>/dev/null || true

# --- wg_allow: NEW rule bucket (left empty here; backend adds per-subnet/per-link NEW rules) ---
nft 'flush chain inet dcv wg_allow' 2>/dev/null || true

# --- NAT table: masquerade WG subnet out of WAN_IF ---
nft list table ip nat >/dev/null 2>&1 || nft add table ip nat
nft 'add chain ip nat prerouting  { type nat hook prerouting  priority -100; }' 2>/dev/null || true
nft 'add chain ip nat postrouting { type nat hook postrouting priority  100; }' 2>/dev/null || true
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

echo "[init] adding ip route for ${WG_ADDRESS_CIDR} via ${WG_IF}..."
ip route replace "${WG_DEFAULT_SUBNET}" dev "${WG_IF}" || true

echo "[init] setting up tcpdump capture on ${WG_IF}..."
# --- tcpdump on wg interface (size-rotating ring) ---
CAP_DIR="${CAP_DIR:-/var/log/captures}"
WG_IF="${WG_IF:-wg0}"

mkdir -p "$CAP_DIR"

TCPDUMP_FILE_MB="${TCPDUMP_FILE_MB:-50}"   # rotate each 50 MB
TCPDUMP_RING_FILES="${TCPDUMP_RING_FILES:-20}" # keep 20 files (max ~1 GB pre-compress)
TCPDUMP_SNAPLEN="${TCPDUMP_SNAPLEN:-128}"
TCPDUMP_FILTER="${TCPDUMP_FILTER:-(tcp or udp)}"

nohup tcpdump -i "$WG_IF" -n -s "$TCPDUMP_SNAPLEN" \
  -C "$TCPDUMP_FILE_MB" -W "$TCPDUMP_RING_FILES" \
  -w "$CAP_DIR/wg-%Y%m%d-%H%M%S.pcap" -z gzip \
  $TCPDUMP_FILTER >/dev/null 2>&1 &
echo "[init] tcpdump running on $WG_IF -> $CAP_DIR (size-rotating, gzip)."


echo "[init] WireGuard up. Starting backend on ${BACKEND_PORT}…"
exec uvicorn backend.main:app --host 0.0.0.0 --port "${BACKEND_PORT}"