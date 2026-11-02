#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import paramiko
HOST, USER, PASS = "191.40.37.234", "root", "REDACTED-ROTATE-ME"
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, 22, USER, PASS, timeout=25, banner_timeout=45, auth_timeout=45, allow_agent=False, look_for_keys=False)
cmd = ("python3 -c \"import sqlite3;c=sqlite3.connect('/opt/mood/mood.db');"
       "c.execute(\\\"DELETE FROM moods WHERE uid='deploy-test'\\\");c.commit();"
       "print('deleted rows=',c.total_changes);c.close()\"")
i,o,e = ssh.exec_command(cmd, timeout=30)
print(o.read().decode("utf-8","ignore").strip(), e.read().decode("utf-8","ignore").strip())
# 验证 today 已清空
i,o,e = ssh.exec_command("curl -s --max-time 5 http://127.0.0.1:8325/mood/api/today", timeout=30)
print("today now:", o.read().decode("utf-8","ignore").strip())
ssh.close()
