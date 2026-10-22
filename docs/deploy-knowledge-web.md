# 私人知识库编辑网站

## 当前部署

- 地址：`https://second.brainpowerai.com.cn/`
- DNSPod：`second` 的 A 记录指向 `101.34.203.35`
- Ubuntu 目录：`/home/ubuntu/mysecondbrain-web`
- 服务：`mysecondbrain-web.service`，单进程 Uvicorn 监听 `127.0.0.1:8789`
- 入口：`knowledge_web.py`，只提供文章查看、搜索及标题、标签、正文编辑
- Caddy：`/home/ubuntu/caddy/Caddyfile`，为整个 `second.brainpowerai.com.cn` 站点设置 HTTPS 和 Basic Auth
- 登录名：`dan`；密码保存在服务器 `/home/ubuntu/.config/mysecondbrain-web/password`，不写入仓库
- 每日 04:10 运行备份，保留最近 14 份于 `/home/ubuntu/backups/mysecondbrain-web`

网页使用独立的最小依赖文件 `requirements-knowledge-web.txt`。不运行原 `main.py`，也不加载 API Key、智能体、播客队列或语音模型。服务器无需 `.env`。
`easynote.brainpowerai.com.cn` 已移除知识库代理配置。写入请求只接受来自 `https://second.brainpowerai.com.cn` 的浏览器来源。

## 数据边界

首次上线从本机做了 SQLite 在线快照，并复制 `static/scripts/` 和 `static/images/`。这三个位置组成网页的完整可编辑数据。网页保存的正文写回服务器的 Markdown 文件；标题和标签写回服务器的 SQLite 数据库。

**上线后服务器是网页版的唯一写入源。** 本机 `data/knowledge.db` 与服务器数据库不会自动双向同步。本机继续生成的新文章不会自动出现在网站；之后若要导入，必须设计按文章 ID 的增量导入，不能用本机旧数据库整体覆盖服务器。历史音频与逐字稿不在编辑网站范围内，未迁移。

## 更新代码

将以下文件部署到服务目录对应路径：`knowledge_web.py`、`requirements-knowledge-web.txt`、`knowledge_assets/`、`templates/knowledge_library.html`、`templates/knowledge_article.html`、`services/db.py`、`scripts/backup_knowledge_web.py`。更新依赖后重启服务：

```bash
cd /home/ubuntu/mysecondbrain-web
.venv/bin/python -m pip install -r requirements-knowledge-web.txt
sudo systemctl restart mysecondbrain-web.service
sudo systemctl status mysecondbrain-web.service
```

更新代码时不要覆盖服务器 `data/` 或 `static/scripts/`，否则会丢失网页编辑成果。

## 验收与备份

1. 未登录访问首页和 `/assets/knowledge.css` 应返回 401。
2. 登录后首页列出文章，搜索及常用标签筛选能找到文章；深色模式在两个页面保持一致。
3. 打开文章可看到标题、标签和正文；切换到编辑模式后左右分栏显示 Markdown 与实时预览。
4. 修改标题、标签、正文并保存，刷新后仍保留；旧页面的正文版本在他处修改后应返回 409，避免覆盖。
5. `/api/chat`、`/generate/url` 应返回 404；直接访问 `8789` 只能从服务器本机进行。
6. 手动备份：

```bash
cd /home/ubuntu/mysecondbrain-web
.venv/bin/python scripts/backup_knowledge_web.py --destination /home/ubuntu/backups/mysecondbrain-web
```

归档包含 `data/knowledge.db`、`static/scripts/`、`static/images/`。恢复前先停止服务，备份当前服务器数据，再将选定归档解压到服务目录，最后启动服务并检查文章数量、图片及编辑功能。
