from flask import Flask, jsonify, render_template_string
import json, os, glob

app = Flask(__name__)

TEMPLATE = '''
<!doctype html><html><head><title>WOPR Approvals</title></head>
<body style="background:#111;color:#0f0;font-family:monospace">
<h1>WOPR Deployment Approval</h1>
{% for dep in deps %}
<div style="border:1px solid #0f0;margin:10px;padding:10px">
<pre>{{ dep|tojson(indent=2) }}</pre>
<a href="/approve/{{dep['id']}}">APPROVE</a> |
<a href="/reject/{{dep['id']}}">REJECT</a>
</div>
{% endfor %}
{% if not deps %}<p>No pending deployments.</p>{% endif %}
</body></html>
'''

PENDING="/opt/wopr-deployment-queue/pending"
APPROVED="/opt/wopr-deployment-queue/approved"
FAILED="/opt/wopr-deployment-queue/failed"

@app.get("/")
def index():
    deps=[]
    for f in glob.glob(os.path.join(PENDING,"*.json")):
        with open(f) as jf: deps.append(json.load(jf))
    return render_template_string(TEMPLATE, deps=deps)

@app.get("/approve/<id>")
def approve(id):
    src=os.path.join(PENDING,f"{id}.json")
    dst=os.path.join(APPROVED,f"{id}.json")
    if os.path.exists(src):
        os.rename(src,dst)
        return jsonify(success=True, approved=id)
    return jsonify(error="not found")

@app.get("/reject/<id>")
def reject(id):
    src=os.path.join(PENDING,f"{id}.json")
    dst=os.path.join(FAILED,f"{id}.json")
    if os.path.exists(src):
        os.rename(src,dst)
        return jsonify(success=True, rejected=id)
    return jsonify(error="not found")

if __name__=="__main__":
    app.run(host="0.0.0.0", port=8080)
