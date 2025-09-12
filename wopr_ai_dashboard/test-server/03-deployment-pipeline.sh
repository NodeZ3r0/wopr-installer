#!/usr/bin/env bash
set -e; umask 022; export DEBIAN_FRONTEND=noninteractive
install -d -m 0755 /opt/wopr-deployment-queue/{pending,approved,deployed,failed} /opt/wopr-approval-dashboard
python3 -m venv /opt/wopr-approval-dashboard/venv
/opt/wopr-approval-dashboard/venv/bin/pip install flask >/dev/null
cat >/opt/wopr-approval-dashboard/app.py <<'PY'
from flask import Flask, jsonify, render_template_string
import json, os, glob
app=Flask(__name__)
T='''<!doctype html><html><body style="background:#111;color:#0f0;font-family:monospace">
<h2>WOPR Approvals</h2>
{% for f in glob.glob("/opt/wopr-deployment-queue/pending/*.json") %}
  {% set dep = open(f).read() %}
  <div style="border:1px solid #0f0;margin:10px;padding:10px">
  <pre>{{ dep }}</pre>
  </div>
{% endfor %}
</body></html>'''
@app.get("/")
def idx(): return render_template_string(T)
if __name__=="__main__": app.run(host="0.0.0.0", port=8080)
PY
cat >/etc/systemd/system/wopr-approval-dashboard.service <<'EOFU'
[Unit]
Description=WOPR Approval Dashboard
After=network.target
[Service]
User=root
WorkingDirectory=/opt/wopr-approval-dashboard
ExecStart=/opt/wopr-approval-dashboard/venv/bin/python /opt/wopr-approval-dashboard/app.py
Restart=always
[Install]
WantedBy=multi-user.target
EOFU
systemctl daemon-reload
systemctl enable --now wopr-approval-dashboard
echo "[*] Pipeline up (dashboard :8080)."
