# 小窝心情（PluginMood）

把每天的心情映射成「天气」并记录 —— 一个给 `sams-house.top` 做的 Halo 插件。

在 UC 个人中心侧边栏加入「小窝心情」入口，跳转到 `/mood/` 独立页面：

- **天气心情**：晴 / 多云 / 小雨 / 雷阵雨 / 彩虹 / 雪 / 星空，每种天气配一句诗意文案。
- **今日心情云图**：看全站今天大家都是什么心情（占比 + 大家写下的话）。
- **我的心情日历**：自己的心情时间线（最近 84 天色块），以及**连续打卡**天数。
- **身份**：登录后跟随 Halo 账号（跨设备）；未登录用本机 UUID（仅存这台设备）。

## 目录结构

```
plugin/                   Halo 插件本体
  plugin.yaml             插件描述（name: PluginMood）
  src/main/java/.../MoodPlugin.java   极简插件入口（仅作载体）
  src/main/resources/console/          UC 路由入口（跳 /mood/）
  src/main/resources/plugin.yaml
  ui/                     前端 UI 源码（Vue + Vite，可选，main.js 已预构建）
  build.py / pack.py      编译 + 打包 jar
  install.py              上传安装并启用插件（需 halo-cred.json）
server.py                 心情后端（纯标准库，SQLite，监听 127.0.0.1:8323）
static/index.html         前端页面（自包含，无外部依赖）
add-menu.py / link-menu.py 把「小窝心情」挂到站点主菜单
deploy/                   部署参考（systemd / nginx / scp 脚本）
```

## 构建插件 jar

```bash
cd plugin
python build.py          # 编译 Java 类（需要 JDK，见 build.py 里的 JDK_DIR）
python pack.py           # 打包 dist/PluginMood-0.1.0.jar
```

> 不想本地构建也可直接用 `plugin/src/main/resources/console/main.js`（已预构建）。

## 安装插件

```bash
# 1) 上传并启用
python plugin/install.py
# 2) 挂到站点主菜单
python add-menu.py
python link-menu.py
```

`install.py` 会读 `C:\Users\sam\WorkBuddy\2026-10-13-21-16-59\tools\halo-cred.json` 登录 Halo，
可按需改成你的凭据路径。

## 启动后端

```bash
# 默认 127.0.0.1:8323，可用环境变量覆盖
MOOD_LISTEN=127.0.0.1 MOOD_PORT=8323 python server.py
```

数据库写入 `mood.db`（已 gitignore）。

## 接入 nginx（参考 deploy/sams-house.mood.nginx.conf）

```nginx
location = /mood/ { proxy_pass http://127.0.0.1:8323/mood/; }
location /mood/api/ { proxy_pass http://127.0.0.1:8323; }
```

## 一键部署到服务器（参考 deploy/deploy.py）

设置环境变量 `MOOD_SSH_HOST / MOOD_SSH_USER / MOOD_SSH_PASS`，然后：

```bash
python deploy/deploy.py
```

会把 `server.py` + `static/` 传到服务器并 `systemctl restart mood`，配套 `deploy/mood.service`。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/mood/api/health` | 健康 |
| GET | `/mood/api/me` | 当前登录用户（best-effort） |
| POST | `/mood/api/log` | 记录今日心情 `{uid, weather, note}` |
| GET | `/mood/api/today` | 全站今日心情云图 |
| GET | `/mood/api/calendar?uid=` | 某用户的心情日历 |

## 说明

本仓库由本地工程导入，构建产物（`build/`、`dist/*.jar`）、依赖（`node_modules/`）、
数据库（`*.db`）、日志（`.log`）等已通过 `.gitignore` 排除。
