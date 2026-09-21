# ADR-0001：Stockfish 经 FastMCP 注册为 MCP 工具

## Context

需要一个能对整盘棋做逐着评估的引擎能力。Stockfish 是现成的开源引擎，但它是一个本地可执行文件，
而 Dify 的 code 节点无法运行本地二进制，因此必须把这个能力封装成一个**外部服务**，再让工作流调用。

可选的封装方式有两种：MCP（Model Context Protocol）服务，或 FastAPI + OpenAPI 自定义工具。

## Decision

用 **FastMCP** 编写一个 MCP 服务，内部用 UCI 协议驱动 Stockfish、配合 `python-chess` 解析 PGN/FEN，
以 SSE 方式对外暴露（`host.docker.internal:9002/sse`）。在 Dify 的【工具 → MCP】中注册为自定义工具，
在 Chatflow 里用【工具】节点调用。

暴露的三个工具：

| 工具 | 用途 |
|---|---|
| `analyze_game` | 整盘逐着分析，返回胜率变化、分类与关键分歧点 |
| `best_moves` | 单一局面的引擎候选着法（MultiPV） |
| `evaluate_position` | 单一局面的白方胜率与最佳着法 |

## Considered

- **FastAPI + OpenAPI 自定义工具**：同样可行，但工具 schema 需要自己维护，且不如 MCP 通用——
  MCP 服务写好之后，任何支持 MCP 的宿主都能直接复用。
- **Dify 内置 code 节点直接跑引擎**：不可行，沙箱环境跑不了本地二进制，也没有运行几分钟的预算。

## Consequences

- 需要一个常驻的 MCP 服务（Python ≥ 3.10），供 Dify 经 `host.docker.internal:9002` 调用。
- 失败点集中在三处：① Stockfish 二进制是否就位 ② MCP 服务与 Dify 的连通性 ③ LLM 的解释质量。
- 工具的 `description` 要写得详尽，帮助模型判断"什么时机该调用哪个工具"。
- 端口使用 9002（9000 常被 RagFlow 的 MinIO 占用）。
