#!/usr/bin/env python3
import json, os, shutil, subprocess, time, hashlib
from datetime import datetime
from pathlib import Path

class DeploymentQueueManager:
    def __init__(self):
        self.queue_dir = Path("/opt/wopr-deployment-queue")
        self.backup_dir = Path("/mnt/backups/incremental")
        self.pending_dir = self.queue_dir / "pending"
        self.approved_dir = self.queue_dir / "approved"
        self.deployed_dir = self.queue_dir / "deployed"
        self.failed_dir = self.queue_dir / "failed"

    def create_incremental_backup(self, deployment):
        deployment_id = deployment['id']
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        name = f"{deployment_id}_backup_{ts}"
        path = self.backup_dir / "pre-deployment" / name
        path.mkdir(parents=True, exist_ok=True)
        targets = [
            f"/etc/systemd/system/wopr-app@{deployment['app']}.service",
            f"/opt/{deployment['app']}"
        ]
        if 'docker_compose' in deployment:
            targets.append(f"/opt/wopr-apps/{deployment['app']}/docker-compose.yml")
        manifest = {"backup_name": name, "files_backed_up": [], "checksums": {}}
        for t in targets:
            try:
                if os.path.isdir(t):
                    dst = path / os.path.basename(t)
                    if os.path.exists(t):
                        shutil.copytree(t, dst)
                        manifest["files_backed_up"].append(f"{t}/ (directory)")
                else:
                    dst = path / os.path.basename(t)
                    if os.path.exists(t):
                        shutil.copy2(t, dst)
                        with open(t, "rb") as f:
                            import hashlib
                            manifest["checksums"][t] = hashlib.sha256(f.read()).hexdigest()
                        manifest["files_backed_up"].append(t)
            except Exception as e:
                print(f"backup fail {t}: {e}")
        with open(path / "backup_manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
        return path, manifest

    def apply_systemd(self, dep):
        app = dep['app']
        port = int(dep.get('port', 8000))
        app_dir = f"/opt/{app}"
        os.makedirs(app_dir, exist_ok=True)

        if 'app_source' in dep:
            for rel, content in dep['app_source'].items():
                p = Path(app_dir) / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding='utf-8')

        reqs = dep.get('requirements_txt')
        if reqs:
            Path(app_dir, 'requirements.txt').write_text(reqs, encoding='utf-8')
            subprocess.run(['python3', '-m', 'venv', 'venv'], cwd=app_dir, check=True)
            subprocess.run([f'{app_dir}/venv/bin/pip', 'install', '--upgrade', 'pip', 'wheel'], check=True)
            subprocess.run([f'{app_dir}/venv/bin/pip', 'install', '-r', 'requirements.txt'], cwd=app_dir, check=True)

        Path(app_dir, 'gunicorn.conf.py').write_text(
            f'bind = "0.0.0.0:{port}"\nworkers=2\nthreads=2\ntimeout=120\naccesslog="-"\nerrorlog="-"\n',
            encoding='utf-8'
        )
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'enable', f'wopr-app@{app}'], check=False)
        subprocess.run(['systemctl', 'restart', f'wopr-app@{app}'], check=True)

    def apply_compose(self, dep):
        app = dep['app']
        app_dir = f"/opt/wopr-apps/{app}"
        os.makedirs(app_dir, exist_ok=True)
        with open(f"{app_dir}/docker-compose.yml", "w") as f:
            f.write(dep['docker_compose'])
        subprocess.run(['docker', 'compose', 'up', '-d'], cwd=app_dir, check=True)

    def process(self, approved_file):
        with open(approved_file) as f:
            dep = json.load(f)
        dep_id = dep['id']
        print(f"Applying {dep_id}...")
        bpath, manifest = self.create_incremental_backup(dep)
        dep['backup_created'] = str(bpath)
        dep['backup_manifest'] = manifest
        if 'docker_compose' in dep:
            self.apply_compose(dep)
        if dep.get('systemd_service') or dep.get('app_type') in ('flask','asgi'):
            self.apply_systemd(dep)
        dep['status'] = 'deployed_success'
        with open(self.queue_dir / 'deployed' / f"{dep_id}.json", "w") as f:
            json.dump(dep, f, indent=2)
        os.remove(approved_file)
        print(f"OK {dep_id}")

if __name__ == "__main__":
    qm = DeploymentQueueManager()
    print("Queue Manager started (mesh-native)")
    while True:
        for p in qm.approved_dir.glob("*.json"):
            qm.process(p)
        time.sleep(10)
