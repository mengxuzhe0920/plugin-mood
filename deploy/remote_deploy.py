#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SSH 部署小窝心情后端到服务器：上传 server.py + static，装 systemd，改 nginx，重载，自检。"""
import os, paramiko, socket, time, datetime

HOST, USER, PASS = "191.40.37.234", "root", "REDACTED-ROTATE-ME"
MOOD_PORT = "8325"
LOCAL = os.path.dirname(os.path.abspath(__file__))   # deploy/
ROOT = os.path.dirname(LOCAL)                          # plugin-mood/
REMOTE_DIR = "/opt/mood"
VHOST = "/www/server/panel/vhost/nginx/sams-house.top.conf"

ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("[1] 连接服务器 ...")
ssh.connect(HOST, 22, USER, PASS, timeout=25, banner_timeout=45, auth_timeout=45, allow_agent=False, look_for_keys=False)
sftp = ssh.open_sftp()

def sh(cmd, timeout=60):
    i,o,e = ssh.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8","ignore").strip()+"\nERR:"+e.read().decode("utf-8","ignore").strip()

def backup_remote(path):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    ssh.exec_command("cp -p %s %s.bak-%s 2>/dev/null; echo ok" % (path, path, ts))

# ---- 2) 上传 server.py（先备份旧版） ----
print("[2] 上传 server.py ...")
backup_remote(os.path.join(REMOTE_DIR, "server.py"))
ssh.exec_command("mkdir -p %s/static %s/logs" % (REMOTE_DIR, REMOTE_DIR))
sftp.put(os.path.join(ROOT, "server.py"), os.path.join(REMOTE_DIR, "server.py"))
print("    server.py put")

# ---- 3) 上传 static/ ----
print("[3] 上传 static/ ...")
for dirpath, _dirs, files in os.walk(os.path.join(ROOT, "static")):
    rel = os.path.relpath(dirpath, os.path.join(ROOT, "static"))
    rdir = REMOTE_DIR + "/static" if rel == "." else os.path.join(REMOTE_DIR, "static", rel)
    ssh.exec_command("mkdir -p %s" % rdir)
    for fn in files:
        sftp.put(os.path.join(dirpath, fn), os.path.join(rdir, fn))
        print("    put", os.path.join(rdir, fn))
sftp.close()

# ---- 4) 写 systemd 服务并启用 ----
print("[4] 写 mood.service 并启用 ...")
svc = """[Unit]
Description=SamHouse Mood Service (小窝心情)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/mood
Environment=PYTHONUNBUFFERED=1
Environment=MOOD_LISTEN=127.0.0.1
Environment=MOOD_PORT=%s
ExecStart=/usr/bin/python3 /opt/mood/server.py
Restart=always
RestartSec=5
StandardOutput=append:/opt/mood/logs/server.log
StandardError=append:/opt/mood/logs/server.err.log

[Install]
WantedBy=multi-user.target
""" % MOOD_PORT
ssh.exec_command("cat > /etc/systemd/system/mood.service <<'EOF'\n%sEOF\n" % svc)
sh("systemctl daemon-reload")
sh("systemctl enable mood")
r = sh("systemctl restart mood; sleep 2; systemctl is-active mood")
print("    mood active:", r.splitlines()[0])

# ---- 5) 改 nginx vhost，插入 MOOD 块 ----
print("[5] 修改 nginx vhost ...")
backup_remote(VHOST)
with ssh.open_sftp() as s:
    cfg = s.open(VHOST, "r").read().decode("utf-8")
if "#MOOD-START" in cfg:
    print("    已存在 #MOOD-START，跳过插入")
else:
    block = """
    #MOOD-START (WorkBuddy 2026-11-02)
    location = /mood {
        return 301 /mood/;
    }
    location ^~ /mood/ {
        proxy_pass http://127.0.0.1:%s;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_cache off;
        add_header Cache-Control "no-store" always;
    }
    #MOOD-END
""" % MOOD_PORT
    # 插在 #UC-CHAT-END 之后
    idx = cfg.find("#UC-CHAT-END")
    if idx != -1:
        insert_at = cfg.find("\n", idx) + 1
        cfg = cfg[:insert_at] + block + cfg[insert_at:]
    else:
        cfg = cfg.rstrip() + "\n" + block
    with ssh.open_sftp() as s:
        s.open(VHOST, "w").write(cfg.encode("utf-8"))
    print("    已插入 #MOOD-START 块")
t = sh("nginx -t 2>&1")
print("    nginx -t:", t.splitlines()[0] if t else "?")
if "test is successful" in t or "successful" in t:
    sh("nginx -s reload")
    print("    nginx reloaded")
else:
    print("    [!] nginx 配置测试失败，未重载，请人工检查")

# ---- 6) 自检 ----
print("[6] 自检 ...")
time.sleep(1)
print("    localhost:%s ->" % MOOD_PORT, sh("curl -s --max-time 5 http://127.0.0.1:%s/mood/api/health || echo FAIL" % MOOD_PORT))
print("    via nginx /mood/ ->", sh("curl -s --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1/mood/ || echo FAIL"))
print("    via nginx /mood/api/health ->", sh("curl -s --max-time 5 http://127.0.0.1/mood/api/health || echo FAIL"))
ssh.close()
print("\n[done] 后端部署完成（端口 %s）" % MOOD_PORT)
