# WSnote

本地优先的 Markdown 个人知识库：笔记即文件，混合检索 + RAG 问答，内置检索质量评测。

## 功能特性

WSnote 是一个「clone 即跑」的本地知识库，核心能力：

- **笔记即 Markdown 文件**：内容以磁盘 `notes/*.md` 文件为唯一事实来源（git 友好、可备份、可 diff），SQLite 与向量库只是「搜索索引」。
- **混合检索**：BM25 稀疏检索 + 稠密向量检索，RRF 融合，可选 rerank 重排，返回带来源（笔记 + 小节）的命中块。
- **RAG 问答**：命中块 + LLM 生成回答，回答携带引用（笔记路径 + 小节标题）；无 LLM key 时自动降级为「仅检索」。
- **内置评测 harness**：golden 查询集 + recall@k / MRR / nDCG 指标 + 配置对比报告，检索质量可量化、可回归。
- **文稿导入**：批量导入长文本（粘贴或 `.txt` / `.md` 文件，兼容 Windows GBK 编码），整篇入库或按一级标题拆成多篇，导入即增量索引。
- **AI 整理**：把录音文字稿 / 长文档用 LLM 整理成结构化笔记（面试复盘 / 通用整理 / 会议纪要三种预设），预览后一键存为笔记。
- **音频转文字（ASR）**：上传音频文件（mp3/wav/m4a 等），本地 faster-whisper GPU 加速转写，或 fallback 到 MiMo API；支持「仅转写」和「转写并整理」两种模式。
- **降级可靠**：无 LLM key、无 embedding 模型、无 FAISS 时均可用（自动降级，HTTP 200 而非 500）。

前端四视图：

- **笔记（`/`）**：左侧笔记列表（标题搜索 + 标签 + 一键导入），右侧 vditor Markdown 编辑器，保存即触发增量索引。
- **搜索（`/search`）**：输入检索词，返回命中块，展示来源笔记、小节与相似度得分，关键词高亮、点击跳转原文。
- **问答（`/chat`）**：聊天式提问，回答下方折叠展示引用（可定位到笔记对应小节）；未配置 LLM 时显示降级提示。
- **整理（`/process`）**：粘贴文字稿或上传文件，选整理方式（面试整理 / 通用整理 / 会议纪要）→ LLM 整理成结构化 Markdown → 预览后「保存为笔记」。

## 架构

```mermaid
flowchart LR
  V[Vue3 前端] --> A[FastAPI]
  A --> N[(notes/*.md)]
  A --> S[(SQLite)]
  A --> F[(FAISS)]
  A --> L[LLM 降级链]
```

- `notes/*.md`：磁盘 Markdown，唯一事实来源
- `SQLite`：分块 / FAISS 映射 / 评测记录
- `FAISS`：向量索引（磁盘落盘，`data/index.faiss`）
- `LLM 降级链`：无 key / 超时 → 降级为「仅检索」

数据流：前端保存笔记 → 落盘 `.md` → 增量索引（重新分块 + embedding，更新 SQLite 与 FAISS）；搜索 / 问答 → 混合检索 top-k（BM25 与向量 RRF 融合）→ 可选 rerank → 返回带来源的块；问答用命中块 + LLM 生成回答并携带引用。

## 快速开始

### 后端

```bash
# 1. 安装依赖（二选一）
pip install -e .                 # 可编辑安装（含全部依赖）
# pip install -r requirements.txt  # 无 uv 用户的纯 pip 列表

# 2. 索引笔记（分块 + embedding + 建向量索引）
python scripts/ws ingest

# 3. 启动 API
uvicorn app.main:app --port 8000
```

访问 <http://127.0.0.1:8000/api/notes> 应返回 `{"code":0,"data":[...]}`。

### 配置 LLM(可选,不配则问答降级为「仅检索」)

不配置任何东西就能跑:问答页返回命中块 + 引用并提示 `degraded:true`,不阻塞其他功能。想让问答**真正生成回答**,通过环境变量配置(推荐,key 不进 git):

| 环境变量 | 说明 | 示例 |
|---|---|---|
| `WSNOTE_LLM_API_KEY` | API key(必填) | `sk-xxx` |
| `WSNOTE_LLM_BASE_URL` | OpenAI 兼容端点(缺省 `https://api.deepseek.com`) | `https://token-plan-cn.xiaomimimo.com/v1` |
| `WSNOTE_LLM_MODEL` | 模型名(缺省 `deepseek-chat`) | `mimo-v2.5` |
| `WSNOTE_LLM_TIMEOUT` | 请求超时秒(缺省 20) | `30` |

> 环境变量优先于 `app/core/config.py` 的 `Config` 默认值(`llm_api_key` / `llm_base_url` / `llm_model` / `llm_timeout`),两种方式皆可,OpenAI 兼容协议,适配 DeepSeek / GLM / MiMo / Ollama 等。
> PyCharm:`Run → Edit Configurations → 运行配置 → Environment variables` 里添加对应行。

**embedding 模型三级降级**:① 本地 ONNX 模型(`models/bge-small-zh-v1.5/`,离线可用,`onnxruntime`+`tokenizers` 直接推理,无需 PyTorch)→ ② 在线 `sentence-transformers`(联网自动下载)→ ③ FakeEmbedder(确定性假向量,零依赖兜底)。检索始终可用,仅质量随降级下降。

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 <http://127.0.0.1:5173/>（Vite 已配置 `/api` 代理到 `http://127.0.0.1:8000`）。生产构建：`npm run build`，产物在 `frontend/dist/`。

### CLI

```bash
python scripts/ws ingest --rebuild      # 全量重建索引
python scripts/ws status                # 索引状态（JSON）
python scripts/ws search "关键词" -k 5   # 混合检索
python scripts/ws eval --golden eval/golden.json --configs '[{"chunk_size":512}]'
```

> **Windows 终端中文乱码？** 数据层与 API 全部显式 UTF-8，乱码只出现在终端显示：CLI 已强制 stdout UTF-8（Git Bash / PyCharm 终端 / Windows Terminal 直接正常）；若用传统 cmd，先 `chcp 65001` 或在环境变量设 `PYTHONUTF8=1` 即可。

## 评测报告

评测集 `eval/golden.json`（24 条中文查询，标注相关块），运行 `python scripts/ws eval` 输出 Markdown 对比报告。本仓库当前实测：

```
# WSnote 检索质量评测报告

| 配置 | recall@5 | recall@10 | mrr@5 | mrr@10 | ndcg@5 | ndcg@10 |
|---|---|---|---|---|---|---|
| chunk_size=512 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
```

> 该报告使用本地 ONNX 版 `bge-small-zh-v1.5`（离线语义向量）。对比 embedding 降级为 FakeEmbedder 时（`recall@5 0.9375 / mrr@5 0.5028`），真实语义向量让检索达到满分。

## 目录速览

```
WSnote/
├── pyproject.toml          # 依赖与 pytest 配置
├── requirements.txt        # 无 uv 用户的纯 pip 依赖
├── README.md
├── LICENSE
├── eval/golden.json        # 检索评测集（24 条查询）
├── notes/                  # 示例笔记（也是 demo 内容）
├── scripts/ws              # CLI 入口（ingest / search / status / eval）
├── app/
│   ├── main.py             # FastAPI 入口
│   ├── api/                # notes / search / chat / tags / index / process
│   ├── core/               # config / db / embeddings / llm 抽象
│   ├── notes/              # 笔记 CRUD（frontmatter）
│   ├── ingest/             # 分块 + embedding + 向量库
│   ├── retrieval/          # BM25 + 混合检索 + rerank
│   ├── chat/               # RAG 问答（引用 + 降级）
│   ├── asr/                # ASR 语音转写（faster-whisper / MiMo API）
│   ├── process/            # 文稿导入 + AI 整理（NoteProcessor）
│   └── eval/               # 指标 + 评测 runner
├── frontend/               # Vue3 + Vite + Element Plus + vditor
└── tests/                  # pytest（63 个用例）
```

> `data/`（SQLite + FAISS 索引）已 git-ignore：索引可随时从 `notes/` 重建，`notes/` 示例笔记随仓库提交。

## 测试

```bash
pip install -e ".[dev]"   # 或 pip install pytest pytest-asyncio httpx
pytest -q
```

当前 63 个测试全部通过。

## License

[MIT](./LICENSE) · Copyright (c) 2026 wshsds00
