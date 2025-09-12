#!/usr/bin/env bash
set -e; umask 077
ROLE="${ROLE:-beacon}"; NEB_IP="${NEB_IP:?set 10.x.x.x}"; NEB_PORT="${NEB_PORT:-4242}"; LIGHTHOUSE_HOST="${LIGHTHOUSE_HOST:-}"; NODE_NAME="${NODE_NAME:-$(hostname -s)}"
install -d -m 0700 /etc/nebula/certs /etc/nebula
if [ ! -f /etc/nebula/certs/ca.key ]; then
  /usr/local/sbin/nebula-cert ca -name "WOPR-Nebula-CA" -out-crt /etc/nebula/certs/ca.crt -out-key /etc/nebula/certs/ca.key
fi
if [ ! -f /etc/nebula/certs/${NODE_NAME}.key ]; then
  /usr/local/sbin/nebula-cert sign -name "${NODE_NAME}" -ip "${NEB_IP}/8" \
    -in-ca /etc/nebula/certs/ca.crt -in-key /etc/nebula/certs/ca.key \
    -out-key /etc/nebula/certs/${NODE_NAME}.key -out-crt /etc/nebula/certs/${NODE_NAME}.crt
fi
cat >/etc/nebula/config.yml <<EOFC
pki:
  ca: /etc/nebula/certs/ca.crt
  cert: /etc/nebula/certs/${NODE_NAME}.crt
  key: /etc/nebula/certs/${NODE_NAME}.key
EOFC
if [ "$ROLE" = "lighthouse" ]; then
cat >>/etc/nebula/config.yml <<EOFL
listen: { host: 0.0.0.0, port: ${NEB_PORT} }
lighthouse: { am_lighthouse: true, hosts: [] }
tun: { dev: nebula0, unsafe_routes: [], tx_queue: 5000 }
firewall:
  conntrack: { tcp_timeout: 12m, udp_timeout: 3m, default_timeout: 10m }
  inbound:  [ { port: any, proto: any, host: any } ]
  outbound: [ { port: any, proto: any, host: any } ]
EOFL
else
  [ -z "$LIGHTHOUSE_HOST" ] && { echo "need LIGHTHOUSE_HOST=<public:port>" >&2; exit 1; }
cat >>/etc/nebula/config.yml <<EOFB
listen: { host: 0.0.0.0, port: 0 }
lighthouse: { am_lighthouse: false, hosts: ["${LIGHTHOUSE_HOST}"] }
punchy: { punch: true }
tun: { dev: nebula0, unsafe_routes: [], tx_queue: 5000 }
firewall:
  conntrack: { tcp_timeout: 12m, udp_timeout: 3m, default_timeout: 10m }
  inbound:  [ { port: any, proto: any, host: any } ]
  outbound: [ { port: any, proto: any, host: any } ]
EOFB
fi
systemctl daemon-reload
systemctl enable --now nebula
echo "[*] Nebula configured (10/8)."
