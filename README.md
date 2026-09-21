# ♟️ AI 国际象棋分析 Agent

> 粘贴一盘棋谱 → Stockfish 引擎逐着评估 → 大模型生成中文复盘报告并给出改进建议

一个把**国际象棋引擎**和**大语言模型**组合起来的智能体项目：让 Stockfish 负责"算棋"（客观评估、找最佳着法），
让 LLM 负责"讲棋"（解释局面、指出错误、给出建议）。引擎保证事实准确，模型保证输出可读。

项目基于 **Dify（工作流编排）+ FastMCP（工具服务）+ RagFlow（知识库）+ Ollama / 云端模型** 搭建，
完整覆盖了"自定义工具封装 → 智能体编排 → 外部知识库接入 → 多端发布"的智能体开发链路。

---

## ✨ 功能

| 能力 | 说明 |
|---|---|
| **整盘复盘** | 输入 PGN 棋谱，逐着计算胜率（win%）损失，标注 `best/exact`、`good`、`inaccuracy`、`mistake`、`blunder` |
| **关键分歧点** | 按"胜率损失"排序，给出最值得复盘的几步及引擎推荐着法 |
| **中文复盘报告** | LLM 依据引擎摘要生成"对局概要 / 关键错误步骤 / 改进建议"结构化报告 |
| **理论答疑** | 提问开局/战术/残局等棋理问题，走 RAG 检索知识库后回答（带引用来源） |
| **多端发布** | Web 应用、网页嵌入（iframe / Script）、后端 API（`/v1/chat-messages`）三种方式 |

---

## 🏗️ 架构

```
                    ┌──────────────────────── Dify Chatflow（编排层）────────────────────────┐
                    │                                                                        │
  用户输入 ──▶ 文档提取器 ──▶ 条件分支（输入是否含着法特征 "1. " ?）                         │
                    │                                                                        │
        ┌───────────┴──── 分支一：棋谱分析 ───────────┐   ┌──── 分支二：理论问答 ──────────┐ │
        │  提取 PGN                                    │   │  知识检索（RagFlow 外部知识库） │ │
        │      ↓                                       │   │        ↓                        │ │
        │  ANALYZE_GAME（MCP 工具）──────────────────┐ │   │  LLM 2                          │ │
        │      ↓                                     │ │   │        ↓                        │ │
        │  整理引擎摘要                               │ │   │  直接回复                       │ │
        │      ↓                                     │ │   └─────────────────────────────────┘ │
        │  LLM（Qwen3.5-27B）                        │ │                                        │
        │      ↓                                     │ │                                        │
        │  直接回复                                   │ │                                        │
        └────────────────────────────────────────────┘ │                                        │
                    └────────────────────────────────────────────────────────────────────────┘
                                    ▲                                   ▲
                                    │ SSE :9002                         │ HTTP :50003
                    ┌───────────────┴───────────────┐   ┌───────────────┴───────────────┐
                    │  FastMCP + Stockfish 引擎      │   │  RagFlow 知识库                │
                    │  analyze_game / best_moves /   │   │  开局原则 / 战术与局面 / 残局技巧 │
                    │  evaluate_position             │   │  （nomic-embed-text 向量化）    │
                    └───────────────────────────────┘   └───────────────────────────────┘
```

**引擎算棋、模型讲棋**：LLM 的上下文只绑定"整理引擎摘要"节点的输出，提示词明确禁止编造棋局内容。

---

## 📁 目录结构

```
.
├── src/
│   ├── analyze.py          # 分析核心：逐着评估、胜率损失、着法分类，可独立 CLI 运行
│   └── mcp_server.py       # FastMCP 服务：把 Stockfish 封装成 3 个 MCP 工具（SSE :9002）
├── knowledge/              # 棋理知识库文档（导入 RagFlow）
│   ├── opening-principles.md
│   ├── tactics-positional.md
│   └── endgame-techniques.md
├── scripts/
│   ├── download_stockfish.py   # 自动下载对应平台的 Stockfish 二进制
│   ├── start_mcp.bat           # Windows 启动脚本（带崩溃自动重启）
│   └── start_mcp.sh            # Linux / macOS 启动脚本
├── examples/
│   ├── opera_game.pgn          # 示例棋局：Opera Game（Morphy 1858，33 半回合，白胜）
│   └── ruy_lopez_short.pgn     # 短局示例（20 步，适合快速验证）
├── docs/
│   ├── CONTEXT.md              # 术语表 / 领域模型
│   ├── PLAN.md                 # 开发排期与关键决策记录
│   ├── TROUBLESHOOTING.md      # 踩坑与解决方案（端口、SSRF、模型选型…）
│   └── adr/                    # 架构决策记录（ADR）
├── .env.example
├── requirements.txt
└── README.md
```

> `engine/`（Stockfish 二进制，约 200MB）不入库，用 `scripts/download_stockfish.py` 自动获取。

---

## 🚀 快速开始

### 0. 前置条件

- Python **3.11+**
- Docker（用于 Dify / RagFlow / Ollama，可选但推荐）
- 约 5GB 可用磁盘（Stockfish 二进制较大）

### 1. 克隆与安装依赖

```bash
git clone https://github.com/HughZzz404/AI-Agent-for-chess.git
cd AI-Agent-for-chess

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 下载 Stockfish 引擎

```bash
python scripts/download_stockfish.py
```

脚本会自动识别平台并下载对应的官方二进制到 `engine/stockfish/`。
也可以手动下载 <https://stockfishchess.org/download/> 后设置环境变量：

```bash
export STOCKFISH_PATH=/path/to/stockfish      # Windows PowerShell: $env:STOCKFISH_PATH="..."
```

### 3. 命令行验证（不依赖 Dify）

先确认引擎分析这块是通的：

```bash
python src/analyze.py examples/ruy_lopez_short.pgn --depth 10 --topn 3
```

输出为 JSON，包含每一着的胜率变化与分类，以及 `top_divergences`（最值得复盘的分歧点）。

### 4. 启动 MCP 工具服务

```bash
# Windows
scripts\start_mcp.bat
# Linux / macOS
bash scripts/start_mcp.sh
```

服务监听 `http://0.0.0.0:9002/sse`，提供三个工具：

| 工具 | 入参 | 用途 |
|---|---|---|
| `analyze_game` | `pgn_text`, `depth`, `topn`, `multipv` | 整盘逐着分析，返回胜负变化与关键分歧点 |
| `best_moves` | `fen`, `depth`, `multipv` | 单一局面的引擎候选着法（MultiPV） |
| `evaluate_position` | `fen`, `depth` | 单一局面的白方胜率与最佳着法 |

> ⚠️ 默认端口是 **9002**（不是 9000）。如果你本机 9000 空闲，可自行改 `src/mcp_server.py` 末尾的 `port=`。
> 注意 9002 是从宿主机访问用的端口；Dify 运行在容器中时请用 `http://host.docker.internal:9002/sse`。

### 5. 部署 Dify / RagFlow / Ollama

按官方文档部署即可：

```bash
# Dify
git clone https://github.com/langgenius/dify.git && cd dify/docker
cp .env.example .env && docker compose up -d

# RagFlow
git clone https://github.com/infiniflow/ragflow.git && cd ragflow/docker
docker compose -f docker-compose.yml up -d

# Ollama（本地模型 + 向量模型）
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
docker exec -it ollama ollama pull qwen2.5:7b
docker exec -it ollama ollama pull nomic-embed-text
```

### 6. 在 Dify 中接入

1. **模型供应商**：`集成 → 模型供应商` 安装 **Ollama** 插件（本地模型）和/或 **OpenAI-API-compatible** 插件（云端模型）。
2. **知识库**：新建知识库，导入 `knowledge/` 下三个 `.md`，Embedding 选 `nomic-embed-text`（或 RagFlow 作为**外部知识库**接入）。
3. **工作流**：新建 **Chatflow** 应用，按上面的架构图搭建节点：
   `用户输入 → 文档提取器 → 条件分支 → 提取 PGN → ANALYZE_GAME（自定义工具）→ 整理引擎摘要（代码节点）→ LLM → 直接回复`
   以及分支二：`知识检索 → LLM 2 → 直接回复`。
4. **自定义工具**：类型选 **MCP（SSE）**，地址填 `http://host.docker.internal:9002/sse`。
   若 Dify 跑在 Docker 里且拦截内网地址，需在 `docker/.env` 中加
   `SSRF_PROXY_ALLOW_PRIVATE_IPS=192.168.65.254/32` 后用 `docker compose up -d` 重建（`restart` 不重读 `.env`）。
5. **提示词**：LLM 节点的上下文绑定"整理引擎摘要"的输出变量，并在提示词中约束
   *只能依据给定的引擎数据作答，数据缺失时写"数据未提供"，禁止编造*。

更多踩坑记录见 [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)。

---

## 💻 使用

### 命令行

```bash
# 分析文件
python src/analyze.py examples/opera_game.pgn --depth 16 --topn 5

# 直接传 PGN 文本
python src/analyze.py "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *" --depth 12

# 分析单个局面（FEN）
python src/analyze.py "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3" --depth 14

# 结果写入文件
python src/analyze.py examples/opera_game.pgn --depth 16 --json-out report.json
```

常用参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--depth` | 16 | 搜索深度，越大越准越慢（33 半回合 @ depth16 约需数分钟） |
| `--multipv` | 3 | 多线路分析条数 |
| `--topn` | 5 | 输出前 N 个关键分歧点 |
| `--engine` | 自动 | Stockfish 路径，优先取 `$STOCKFISH_PATH` |

### 通过 Dify 对话

在 Dify 应用的访问点页可拿到三种发布方式：**Web 应用**、**网页嵌入代码**、**后端 API**。

```bash
curl -X POST "http://<你的Dify地址>/v1/chat-messages" \
  -H "Authorization: Bearer app-xxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
        "inputs": {},
        "query": "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *",
        "response_mode": "blocking",
        "user": "demo"
      }'
```

返回的 `answer` 即复盘报告，`metadata.retriever_resources` 会列出本次引用的知识库片段。

---

## 🔍 实现要点

**为什么用"胜率损失"而不是"丢分"？**
直接用厘兵（centipawn）差值会被将杀分数污染（`mate` 会变成 ±100000，差值失去意义）。
`analyze.py` 用 Lichess 的胜率公式把分数映射到 0–100 的胜率，再计算某一步让本方胜率掉了多少，
天然有界、对将杀安全，阈值分类也更符合人类棋感。

**为什么用 MCP 而不是普通 HTTP 接口？**
MCP（Model Context Protocol）让工具的入参/出参带自描述 schema，Dify 等宿主能自动识别可调用工具，
无需手写一层胶水接口。这里用 FastMCP 把 Stockfish 包成 3 个工具，一次封装多处复用。

**为什么 LLM 节点要单独有一个"整理引擎摘要"代码节点？**
原始逐着数据又长又冗余，直接塞给模型既贵又容易让模型抓不住重点，
所以在代码节点里先汇总成「对局概要 + top 分歧点 + 改进建议素材」再交给 LLM。

---

## 🐛 已知问题

见 [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)，涵盖：

- Ollama 11434 端口落入 Windows 保留段导致容器无法访问（改用 12424）
- Dify SSRF 防护拦截 `host.docker.internal`
- 硅基流动报 `20015 No user query found in messages`
- 7B 级本地模型无视引擎数据编造棋局内容（模型选型教训）
- 端口与 RagFlow 的 MinIO 冲突导致 MCP 从 9000 改到 9002

---

## 📄 License

[MIT](LICENSE)

## 🙏 致谢

- [Stockfish](https://stockfishchess.org/) —— 开源国际象棋引擎
- [python-chess](https://github.com/niklasf/python-chess) —— 棋局解析与引擎通信
- [FastMCP](https://github.com/jlowin/fastmcp) —— MCP 服务框架
- [Dify](https://github.com/langgenius/dify) / [RagFlow](https://github.com/infiniflow/ragflow) / [Ollama](https://github.com/ollama/ollama)
