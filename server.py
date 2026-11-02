#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小窝心情 —— 挂载在 sams-house.top/mood 的心情记录服务（纯标准库）

把每天的心情映射成「天气」并记录，可看全站今日心情云图与自己的心情日历。

- 身份：优先复用 Halo 站点 cookie（resolve_user）；未登录则用前端生成的本地 UUID。
- 存储：SQLite（mood.db，每个 uid 每天一条，重复记录覆盖）
- HTTP：http.server.ThreadingHTTPServer
- 部署：127.0.0.1:8323，由 nginx 反代 /mood/

心情类型（weather）：
  sunny    晴    ☀️  轻盈开心
  cloudy   多云  ⛅  平淡平静
  rain     小雨  🌧️  低落想哭
  thunder  雷阵雨 ⛈️  烦躁愤怒
  rainbow  彩虹  🌈  感恩治愈
  snow     雪    ❄️  安静孤独
  star     星空  🌌  夜思期待

接口：
  GET  /mood/                      → 前端 HTML
  GET  /mood/api/health            → 健康
  GET  /mood/api/me                → 当前登录用户（best-effort，Halo cookie）{ok, logged_in, user?}
  POST /mood/api/log               → 记录今日心情 {uid, weather, note} → {ok, date}
  GET  /mood/api/today             → 全站今日心情云图 {ok, date, total, distribution, top, notes[]}
  GET  /mood/api/calendar?uid=      → 某用户的心情日历 {ok, uid, days[], streak}
"""
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------- 配置 ----------
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "mood.db")
STATIC_DIR = os.path.join(BASE, "static")
HALO_INTERNAL = os.environ.get("MOOD_HALO_INTERNAL", "http://127.0.0.1:8090")
LISTEN = os.environ.get("MOOD_LISTEN", "127.0.0.1")
PORT = int(os.environ.get("MOOD_PORT", "8323"))
SESSION_CACHE_TTL = 60

WEATHERS = {
    "sunny": "晴", "cloudy": "多云", "rain": "小雨", "thunder": "雷阵雨",
    "rainbow": "彩虹", "snow": "雪", "star": "星空",
}
NOTE_MAX = 140

# ---------- DB ----------
SCHEMA = """
CREATE TABLE IF NOT EXISTS moods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT NOT NULL,
    date TEXT NOT NULL,
    weather TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_mood_uid_date ON moods(uid, date);
"""

_db_lock = threading.Lock()
_db = sqlite3.connect(DB_PATH, check_same_thread=False)
_db.row_factory = sqlite3.Row
with _db_lock:
    _db.executescript(SCHEMA)


def db_exec(sql, params=()):
    with _db_lock:
        cur = _db.execute(sql, params)
        _db.commit()
        return cur


def db_query(sql, params=()):
    with _db_lock:
        cur = _db.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def today_str():
    return time.strftime("%Y-%m-%d", time.localtime())


# ---------- Halo 身份识别（best-effort） ----------
_session_cache: dict = {}
_cache_lock = threading.Lock()


def resolve_user(cookie_header: str):
    """把浏览器 cookie 转发给 Halo 内部端口，拿当前用户。失败/未登录返回 None。"""
    if not cookie_header:
        return None
    now = time.time()
    with _cache_lock:
        cached = _session_cache.get(cookie_header)
        if cached and cached[0] > now:
            return cached[1]
    try:
        last_err = None
        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    f"{HALO_INTERNAL}/apis/api.console.halo.run/v1alpha1/users/-",
                    headers={"Cookie": cookie_header, "User-Agent": "mood/1.0"},
                )
                ctx = ssl_create()
                with urllib.request.urlopen(req, timeout=4, context=ctx) as resp:
                    body = resp.read().decode("utf-8", "ignore")
                j = json.loads(body)
                u = j.get("user") or {}
                meta = u.get("metadata") or {}
                spec = u.get("spec") or {}
                name = meta.get("name")
                if not name or name == "anonymousUser":
                    return None
                user = {
                    "name": name,
                    "displayName": spec.get("displayName") or name,
                    "avatar": spec.get("avatar") or "",
                }
                with _cache_lock:
                    _session_cache[cookie_header] = (now + SESSION_CACHE_TTL, user)
                return user
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    return None
                last_err = e
            except Exception as e:
                last_err = e
            if attempt < 1:
                time.sleep(0.3)
        print(f"[resolve_user] {type(last_err).__name__}: {last_err}", flush=True)
        return None
    except Exception as e:
        print(f"[resolve_user] {type(e).__name__}: {e}", flush=True)
        return None


def ssl_create():
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ---------- HTTP Handler ----------
def _json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "SamMood/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # 静默

    # ---------- 工具 ----------
    def _send(self, code, body=b"", content_type="text/plain; charset=utf-8", extra_headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        if body:
            try:
                self.wfile.write(body)
            except Exception:
                pass

    def _send_json(self, obj, code=200):
        self._send(code, _json_bytes(obj), "application/json; charset=utf-8")

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _read_json(self):
        body = self._read_body()
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8", "ignore"))
        except Exception:
            return {}

    def _current_user(self):
        cookie = self.headers.get("Cookie") or ""
        return resolve_user(cookie)

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---------- GET ----------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 前端
        if path == "/mood":
            self.send_response(301)
            self.send_header("Location", "/mood/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path in ("/mood", "/mood/"):
            html_path = os.path.join(STATIC_DIR, "index.html")
            try:
                with open(html_path, "rb") as f:
                    body = f.read()
                self._send(200, body, "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, "not found")
            return

        if path == "/mood/api/health":
            self._send_json({"ok": True, "ts": int(time.time())})
            return

        if path == "/mood/api/me":
            user = self._current_user()
            if user:
                self._send_json({"ok": True, "logged_in": True, "user": user})
            else:
                self._send_json({"ok": True, "logged_in": False})
            return

        if path == "/mood/api/today":
            self._send_json(self._today_cloud())
            return

        m = re.match(r"^/mood/api/calendar$", path)
        if m:
            uid = (query.get("uid", [""])[0] or "").strip()
            if not uid:
                self._send_json({"ok": False, "detail": "uid required"}, 400)
                return
            self._send_json(self._calendar(uid))
            return

        self._send(404, "not found")

    # ---------- POST ----------
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/mood/api/log":
            body = self._read_json()
            uid = str(body.get("uid") or "").strip()
            weather = str(body.get("weather") or "").strip()
            note = str(body.get("note") or "").strip()
            if not uid:
                self._send_json({"ok": False, "detail": "uid required"}, 400)
                return
            if weather not in WEATHERS:
                self._send_json({"ok": False, "detail": "bad weather"}, 400)
                return
            if len(note) > NOTE_MAX:
                note = note[:NOTE_MAX]
            date = today_str()
            ts = int(time.time())
            # 每个 uid 每天一条：存在则覆盖
            db_exec(
                """INSERT INTO moods(uid, date, weather, note, created_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(uid, date) DO UPDATE SET
                     weather=excluded.weather,
                     note=excluded.note,
                     created_at=excluded.created_at""",
                (uid, date, weather, note, ts),
            )
            self._send_json({"ok": True, "date": date, "weather": weather})
            return

        self._send(404, "not found")

    # ---------- 业务逻辑 ----------
    def _today_cloud(self):
        date = today_str()
        rows = db_query(
            "SELECT weather, COUNT(*) AS c FROM moods WHERE date=? GROUP BY weather",
            (date,),
        )
        dist = {w: 0 for w in WEATHERS}
        total = 0
        for r in rows:
            dist[r["weather"]] = r["c"]
            total += r["c"]
        top = None
        if total:
            top = max(dist.items(), key=lambda kv: kv[1])[0]
        # 今天写过心情的人（匿名），取最近几条带文字的
        notes = db_query(
            "SELECT weather, note, created_at FROM moods WHERE date=? AND note<>'' "
            "ORDER BY created_at DESC LIMIT 12",
            (date,),
        )
        return {
            "ok": True,
            "date": date,
            "total": total,
            "distribution": dist,
            "top": top,
            "notes": [
                {"weather": n["weather"], "note": n["note"], "ts": n["created_at"]}
                for n in notes
            ],
        }

    def _calendar(self, uid):
        rows = db_query(
            "SELECT date, weather, note FROM moods WHERE uid=? ORDER BY date ASC",
            (uid,),
        )
        days = [
            {"date": r["date"], "weather": r["weather"], "note": r["note"]}
            for r in rows
        ]
        # 连续打卡：从今天往前数（今天没记则允许到昨天）
        streak = 0
        date_set = {r["date"] for r in rows}
        # 从今天开始倒推
        t = time.localtime()
        # 今天若未记录，则从昨天起算
        y, mo, day = t.tm_year, t.tm_mon, t.tm_mday
        # 先尝试今天
        import datetime
        cur = datetime.date(y, mo, day)
        if cur.isoformat() not in date_set:
            cur = cur - datetime.timedelta(days=1)
        while cur.isoformat() in date_set:
            streak += 1
            cur = cur - datetime.timedelta(days=1)
        return {"ok": True, "uid": uid, "days": days, "streak": streak}


# ---------- 启动 ----------
def main():
    server = ThreadingHTTPServer((LISTEN, PORT), Handler)
    server.daemon_threads = True
    print(f"[mood] listening on http://{LISTEN}:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
