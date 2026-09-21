# ADR-0002：经 Dify 外部知识库 API 接入 RagFlow，使用原生知识检索节点

## Context

项目需要为"理论性问题"（开局原则、战术、残局等）提供有依据的回答，因此要有知识库检索能力。
RagFlow 提供了专为 Dify 开发的集成接口，可以让 Dify 直接把 RagFlow 的知识库当作自己的外部知识库使用。

可选的接入方式有两种：使用 Dify 的【外部知识库 API】+ 原生【知识检索】节点，
或自己写一个自定义工具去调 RagFlow 的检索接口。

## Decision

在 Dify 的【知识库 → 外部知识库 API】中添加 RagFlow：

- Endpoint：`http://host.docker.internal:50003/api/v1/dify`
- 填入 RagFlow 侧创建的 API Key 与知识库 ID

然后在 Chatflow 中用【知识检索】节点绑定该外部知识库，随用户提问（`sys.query`）检索棋理内容。

## Considered

- **自定义工具调 `/api/v1/retrieval`**：可行，但要自己维护检索参数与结果格式，
  且绕过了 Dify 原生的检索节点，无法利用 Dify 的引用展示、重排序等能力。
- **Dify 内置知识库（文档直接入库）**：更简单，但解析/分块/检索能力不如 RagFlow。
  作为内存不足、RagFlow 无法启动时的退路保留。

## Consequences

- 需要在 RagFlow 创建 API Key（弹窗关闭后不再显示，须立即复制），并记录知识库 ID。
- **常见坑**：若 Dify 中添加外部知识库失败，先填 `http://host.docker.internal:50003`
  （不带 `/api/v1/dify`）保存成功，再改为完整地址二次保存；
  Dify 会自动拼接 `/retrieval/health` 做连通性校验，端点不能重复带 `/retrieval`。
- 若 Dify 报 SSRF 拦截，需在 `docker/.env` 中放行内网地址
  （`SSRF_PROXY_ALLOW_PRIVATE_IPS=192.168.65.254/32`）并 `docker compose up -d` 重建容器。
- 检索依赖 Dify ↔ RagFlow 连通（`host.docker.internal:50003`）以及 Ollama 的 embedding 模型。
- 知识库内容变更后需**重新发布应用**才生效。
