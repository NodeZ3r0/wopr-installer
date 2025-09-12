#!/usr/bin/env bash
set -e; umask 022; export DEBIAN_FRONTEND=noninteractive
NEB_IF="${NEBULA_INTERFACE:-nebula0}"
apt-get update -y && apt-get install -y suricata suricata-update
install -d -m 0755 /etc/suricata/suricata.d
cat >/etc/suricata/suricata.d/wopr.yaml <<EOF
vars:
  address-groups:
    HOME_NET: "[${NEB_IF}]"
EOF
suricata-update update-sources || true
suricata-update || true
systemctl enable suricata
systemctl restart suricata || true
suricata -T || true
echo "[*] Suricata bound to ${NEB_IF}."
