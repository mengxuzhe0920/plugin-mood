#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 server.py + static/ 部署到服务器并重启 mood 服务。

用法：
  set MOOD_SSH_HOST=1.2.3.4
  set MOOD_SSH_USER=root
  set MOOD_SSH_PASS=****
  python deploy/deploy.py

需要 paramiko：pip install paramiko
"""
import os
import sys

try:
    import paramiko
except ImportError:
    sys.exit("请先安装 paramiko：pip install paramiko")

HOST = os.environ.get("MOOD_SSH_HOST")
USER = os.environ.get("MOOD_SSH_USER")
PASS = os.environ.get("MOOD_SSH_PASS")
if not all([HOST, USER, PASS]):
    sys.exit("请设置环境变量 MOOD_SSH_HOST / MOOD_SSH_USER / MOOD_SSH_PASS")

ROOT = os.path.dirname(os.path.abspath(__file__))
LOCAL_SERVER = os.path.join(ROOT, "..", "server.py")
LOCAL_STATIC = os.path.join(ROOT, "..", "static")
REMOTE_DIR = "/opt/mood"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("连接 %s ..." % HOST)
ssh.connect(HOST, 22, USER, PASS, timeout=25, banner_timeout=45,
            auth_timeout=45, allow_agent=False, look_for_keys=False)
sftp = ssh.open_sftp()
ssh.exec_command("mkdir -p %s/static" % REMOTE_DIR)


def put_tree(local_root, remote_root):
    for dirpath, _dirs, files in os.walk(local_root):
        rel = os.path.relpath(dirpath, local_root)
        remote_path = remote_root if rel == "." else os.path.join(remote_root, rel)
        ssh.exec_command("mkdir -p %s" % remote_path)
        for fn in files:
            local_file = os.path.join(dirpath, fn)
            remote_file = os.path.join(remote_path, fn)
            sftp.put(local_file, remote_file)
            print("  put", remote_file)


print("上传 server.py ...")
sftp.put(LOCAL_SERVER, os.path.join(REMOTE_DIR, "server.py"))
print("上传 static/ ...")
put_tree(LOCAL_STATIC, os.path.join(REMOTE_DIR, "static"))
sftp.close()

print("重启 mood 服务 ...")
ssh.exec_command("systemctl restart mood || (cd %s && nohup python3 server.py >/tmp/mood.log 2>&1 &)" % REMOTE_DIR)
ssh.close()
print("[done] 部署完成。访问 https://你的域名/mood/")
