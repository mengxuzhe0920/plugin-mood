#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正部署：清掉反斜杠误建文件，用正斜杠重新上传 server.py + static，重启服务并自检。"""
import os, paramiko, time, datetime

import _secret; HOST, USER, PASS = _secret.HOST, _secret.USER, _secret.PASS
LOCAL = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(LOCAL)
REMOTE_DIR = "/opt/mood"

ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASS, timeout=25, banner_timeout=45, auth_timeout=45, allow_agent=False, look_for_keys=False)

def sh(cmd, timeout=60):
    i,o,e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8","ignore").strip(); err = e.read().decode("utf-8","ignore").strip()
    return out, err

# 清掉旧目录（含反斜杠误建文件），重建
print("[1] 清理并重建 /opt/mood ...")
sh("rm -rf /opt/mood; mkdir -p /opt/mood/static /opt/mood/logs; echo done")

sftp = ssh.open_sftp()
# 上传 server.py（正斜杠远程路径）
local_server = os.path.join(ROOT, "server.py")
print("[2] 上传 server.py (%d bytes) ..." % os.path.getsize(local_server))
sftp.put(local_server, "/opt/mood/server.py")
# 上传 static/index.html
local_static = os.path.join(ROOT, "static", "index.html")
print("[3] 上传 static/index.html (%d bytes) ..." % os.path.getsize(local_static))
sftp.put(local_static, "/opt/mood/static/index.html")
sftp.close()

# 确认文件到位
print("[4] 校验远程文件 ...")
out, _ = sh("ls -l /opt/mood/server.py /opt/mood/static/index.html")
print(out)

# 重启服务
print("[5] 重启 mood 服务 ...")
sh("systemctl daemon-reload; systemctl restart mood; sleep 3")
out, _ = sh("systemctl is-active mood")
print("    mood active:", out)

# 自检
print("[6] 自检 ...")
time.sleep(1)
out, _ = sh("curl -s --max-time 5 http://127.0.0.1:8325/mood/api/health || echo FAIL-8325")
print("    localhost:8325/mood/api/health ->", out)
out, _ = sh("curl -s --max-time 5 http://127.0.0.1/mood/api/health || echo FAIL-NGINX")
print("    via nginx /mood/api/health     ->", out)
out, _ = sh("curl -s --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1/mood/ || echo FAIL")
print("    via nginx /mood/  http_code     ->", out)
ssh.close()
print("\n[done] 修正部署完成")
