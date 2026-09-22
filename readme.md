# 第二大脑计划（MySecondBrain）

一个本地运行的 FastAPI 个人知识库：导入网页、文件和视频内容，生成中文文章、逐字稿与播客，并将播客发布为 RSS。

## 主要能力

- 保存、搜索、编辑和标注知识库文章
- 从 YouTube、Bilibili、抖音及本地文件提取内容
- 优先使用平台字幕或 AI 字幕生成逐字稿和文章
- 可选择保留原始音频；仅在明确开启且没有字幕时使用 Whisper
- 后台任务队列、任务详情、取消和重试
- 生成音频、拆分超大音频并发布到 Cloudflare Pages RSS

## 仓库与本地数据边界

这是一个公开代码仓库。为避免泄露隐私或提交超大文件，下列内容不会进入 Git：

- `.env`：API Key、发布仓库及运行配置
- `brain/`：本地知识图谱数据
- `data/`：SQLite 数据库、Cookie、Whisper 模型及下载的原始媒体
- `static/audio/`：本地生成或下载的音频
- `temp_uploads/`、本地工具和虚拟环境

仓库会保存应用代码、测试、文章脚本、逐字稿、封面图片以及 RSS 元数据。正式发布的音频由 `.env` 中的 `GITHUB_PAGES_REPO` 指向独立发布仓库；当前远程 RSS 为：

<https://podcast-generator-ar1.pages.dev/podcast.xml>

## 在新电脑安装

以下步骤以 macOS 为例。建议使用 Python 3.11 或 3.12。

### 1. 安装基础工具

```bash
xcode-select --install
brew install python ffmpeg git
```

确保新电脑的 GitHub SSH Key 已配置：

```bash
ssh -T git@github.com
```

### 2. 克隆并安装 Python 依赖

```bash
git clone git@github.com:TU-Dan/SecondBrain.git
cd SecondBrain
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. 创建本机配置

```bash
cp .env.example .env
```

编辑 `.env`，至少填写：

```dotenv
DEEPSEEK_API_KEY=你的_Key
GITHUB_PAGES_URL=https://podcast-generator-ar1.pages.dev
GITHUB_PAGES_REPO=git@github.com:TU-Dan/podcast_generator.git
GITHUB_PAGES_BRANCH=gh-pages
```

如需知识图谱向量检索，再填写 `VOYAGE_API_KEY` 或 `OPENAI_API_KEY`。不要提交 `.env`。

### 4. 安装播客平台工具

```bash
bash scripts/setup_podcast_tools_macos.sh
bash scripts/check_podcast_tools.sh
```

Bilibili 或抖音需要登录态时，按需运行：

```bash
bash scripts/capture_douyin_cookie.sh
bash scripts/start_douyin_downloader.sh
```

Bilibili Cookie 放在 `data/cookies/bilibili.txt`。这些 Cookie 只保存在本机。

### 5. 启动服务

```bash
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

打开：

- 知识库：<http://127.0.0.1:8000/>
- 新建播客：<http://127.0.0.1:8000/generate>
- 任务中心：<http://127.0.0.1:8000/tasks>
- 本地 RSS：<http://127.0.0.1:8000/static/podcast.xml>

## 从旧电脑迁移个人数据

GitHub 不保存个人数据库和大音频。需要完整迁移时，先停止两台电脑上的服务，再用移动硬盘、局域网或加密云盘复制以下内容：

```text
.env
data/knowledge.db
brain/
static/audio/
```

如需保留已下载的原始媒体、模型和平台登录态，可额外复制：

```text
data/podcast_media/
data/models/
data/cookies/
```

在新电脑的项目根目录恢复相同路径后再启动服务。无需迁移已发布音频也可以直接订阅远程 RSS；后续发布需要新电脑能够通过 SSH 写入 `GITHUB_PAGES_REPO`。

可用 `rsync` 在局域网中迁移（将主机名和路径替换为实际值）：

```bash
rsync -av --progress old-mac:/path/to/MySecondBrain/data/ ./data/
rsync -av --progress old-mac:/path/to/MySecondBrain/brain/ ./brain/
rsync -av --progress old-mac:/path/to/MySecondBrain/static/audio/ ./static/audio/
scp old-mac:/path/to/MySecondBrain/.env ./.env
```

迁移后执行一次检查：

```bash
bash scripts/check_podcast_tools.sh
python scripts/verify_podcast_fidelity.py
```

## 日常更新

确认本机没有未提交改动后：

```bash
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`.env`、数据库、知识图谱和本地音频不会被 `git pull` 覆盖。

## 开发验证

```bash
python -m unittest discover -s tests -p 'test_podcast_pipeline.py' -v
python -m unittest discover -s tests -p 'test_publish_to_pages.py' -v
python -m unittest discover -s tests -p 'test_article_content.py' -v
python scripts/verify_podcast_fidelity.py
python scripts/verify_youtube_url_normalization.py
python -m py_compile main.py services/*.py packages/content-to-podcast/content_to_podcast/*.py
git diff --check
```
