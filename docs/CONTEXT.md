# Chess Analyzer

国际象棋 AI 分析 Agent。用户上传/粘贴一盘棋谱（PGN），Agent 用 Stockfish 逐步评估、用 LLM 解释关键局面并给出可执行的改进建议。应用类型为 Dify Chatflow，Stockfish 通过 FastMCP 注册为 Dify MCP 工具接入。

## Language

**棋谱（Game record）**:
用户输入的整盘对局记录，以 PGN 文本（粘贴或文件）表达。
*Avoid*: 对局文件、博弈记录

**局面（Position）**:
棋局中某一个确定的棋子分布状态，以 FEN 表达。是"分析的最小单元"。与"整盘对局"相对。
*Avoid*: 棋形

**逐步评估（Per-move evaluation）**:
Stockfish 对每一步着法给出的局面评分（centipawn）与实战着法的评估差（评估值变化量）。
*Avoid*: 引擎打分、分数

**胜率损失（Win% loss）**:
实战着法使本方胜率下降的百分点（0–100，天然有界）。相比裸厘兵差值，它在将杀/终局局面上不会出现爆炸值。
本项目用它把着法分类为 精确/最佳、良好、不精确、失误、昏招。
*Avoid*: 评分损失、掉分、评估差

**分类（Blunder/Inaccuracy classification）**:
按评估差阈值把每步着法归入 精确/最佳/失误/重大错误/昏招 等类别。
*Avoid*: 判断、标签

**最佳替代着法（Best alternative）**:
在关键分歧局面，引擎给出的最优着法，用于和用户实战着法对比。
*Avoid*: 推荐步、最优解

**关键分歧点（Critical divergence）**:
评估差最大的若干局面，Agent 重点展开解释的地方。
*Avoid*: 错棋、重点

**MCP 工具（MCP tool）**:
用 FastMCP 框架（`@mcp.tool`）编写的服务，在 Dify【工具 → MCP】注册，供 Chatflow 的【工具】节点调用。本项目用它把 Stockfish 包装成 `analyze_game` 等工具。
*Avoid*: 插件、API 按钮、外部链接

**LLM 解释输出（Explanation report）**:
LLM 基于引擎数据生成的最终报告：对局概要 → 关键分歧点（附引擎数据）→ 按 开局/中局/残局/战术/局面 归类的改进建议。
*Avoid*: 总结、点评

**知识库（Knowledge base）**:
RagFlow 里存放"开局原则/残局技巧"等小文档集，供 LLM 按当前局面检索相关棋理，作为改进建议的理论依据。与"引擎实测数据"互补。
*Avoid*: 资料库、文档库

**知识检索（Knowledge Retrieval）**:
Dify 原生节点，从绑定的知识库（本项目为 RagFlow 外部知识库）按用户问题取回相关片段。经 Dify【外部知识库 API】连接 RagFlow，使用其专为 Dify 开发的 `/api/v1/dify` 接口。
*Avoid*: 搜索、查资料、自定义检索

**理论依据（Theory grounding）**:
改进建议背后的理由，来源二选一及叠加：① 引擎实测数据（评估分/评估差/最佳着法，事实依据）；② 棋盘理论（知识库检索出的原则 + 静态原则 prompt）。
*Avoid*: 依据、理由

## Decisions

见 `docs/adr/`。
