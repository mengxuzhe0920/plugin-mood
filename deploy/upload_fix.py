import paramiko, os, base64, time

VHOST = "/www/server/panel/vhost/nginx/sams-house.top.conf"
LOCAL = r"C:/Users/sam/WorkBuddy/2026-11-02-20-00-30/plugin-mood/static/index.html"
REMOTE = "/opt/mood/static/index.html"
import _secret; HOST, USER, PASS = _secret.HOST, _secret.USER, _secret.PASS

def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, 22, USER, PASS, timeout=25, banner_timeout=45, auth_timeout=45, allow_agent=False, look_for_keys=False)
    return ssh

def sh(ssh, cmd, timeout=60):
    i,o,e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8","ignore").strip(); err = e.read().decode("utf-8","ignore").strip()
    return out, err

# 1) 上传 index.html（base64 管道，避开 SFTP 子系统）
for attempt in range(3):
    try:
        ssh = connect()
        data = open(LOCAL,"rb").read()
        b64 = base64.b64encode(data).decode()
        i,o,e = ssh.exec_command("base64 -d > " + REMOTE, timeout=60)
        i.write(b64 + "\n"); i.flush(); i.channel.shutdown_write()
        o.read(); err = e.read().decode("utf-8","ignore").strip()
        # 校验远端大小
        out, _ = sh(ssh, "wc -c < " + REMOTE)
        print("[ok] uploaded index.html ->", REMOTE, "remote bytes =", out.strip())
        break
    except Exception as ex:
        print("[retry %d]" % attempt, ex)
        time.sleep(2)
else:
    raise SystemExit("upload failed")

# 2) nginx：MOOD 区域确保 proxy_cache off
out, _ = sh(ssh, "cat " + VHOST)
cfg = out
start = cfg.find("#MOOD-START"); end = cfg.find("#MOOD-END")
if start != -1 and end != -1:
    region = cfg[start:end]
    if "proxy_cache off" not in region:
        new_region = region.replace("proxy_pass http://127.0.0.1:8325;",
                                    "proxy_cache off;\n        proxy_pass http://127.0.0.1:8325;")
        cfg = cfg[:start] + new_region + cfg[end:]
        i,o,e = ssh.exec_command("cat > " + VHOST, timeout=60)
        i.write(cfg.encode()); i.flush(); i.channel.shutdown_write(); o.read()
        print("[ok] added proxy_cache off to mood block")
        out, err = sh(ssh, "nginx -t 2>&1")
        print("[nginx -t]", out, err)
        sh(ssh, "nginx -s reload")
        print("[ok] nginx reloaded")
    else:
        print("[skip] mood block already has proxy_cache off")
else:
    print("[warn] MOOD block not found in vhost")

ssh.close()
print("[done]")
