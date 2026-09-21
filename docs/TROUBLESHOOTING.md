# 踩坑与解决方案

本文记录复现本项目时真实遇到的问题与处理办法，按"现象 → 原因 → 解决"组织。

---

## 1. Stockfish 分析把将杀局面算成"巨大丢分"

**现象**：某些着法被标成 `blunder`，`eval` 差值高达 ±100000，明显不合理。

**原因**：直接用厘兵（centipawn）差值衡量着法质量。Stockfish 对"将杀"返回的不是厘兵分而是一个
特殊标记，若按数值处理就会变成 ±100000，差值失去意义；而在将杀/僵局等终局局面上引擎不再搜索，
分数也会跳变。

**解决**：`src/analyze.py` 改用**胜率损失**衡量——

1. 用 Lichess 的胜率公式把厘兵分映射到 0–100 的胜率区间（天然有界）；
2. 将杀单独处理：本方将杀对手 → 100%，被将杀 → 0%，僵局 → 50%；
3. 某着法的质量 = 走子前本方胜率 − 走子后本方胜率，并 clamp 掉 <0.3 的搜索噪声。

---

## 2. `AttributeError: 'int' object has no attribute 'is_mate'`

**现象**：调用 MCP 的 `best_moves` / `evaluate_position` 时服务抛异常，Dify 工作流里工具节点一直转圈。

**原因**：python-chess 1.11.2 中 `PovScore.pov(color)` 返回的是 **int（厘兵分）或 `chess.engine.Mate`**，
而不是旧版的 `Score` 对象。因此对它继续调用 `.score()` / `.is_mate()` / `.pov()` 都会失败。

**解决**：统一用 `isinstance(pov, int)` 分支处理，`Mate` 用 `.mate()` 取步数并映射到 ±100000。
参见 `src/analyze.py` 的 `white_winpct_from_pov()` 与 `src/mcp_server.py` 的 `best_moves()`。

---

## 3. Ollama 在容器里"连不上"（11434 端口）

**现象**：Ollama 跑在宿主机，Dify / RagFlow 容器内访问 `host.docker.internal:11434` 报
`Connection refused`；宿主机上 `curl localhost:11434` 却正常。

**原因**：**11434 落在 Windows（WSL2）动态保留端口段 11433–11532 内**，
Docker 的端口代理无法稳定绑定该端口，容器侧的转发因此失效。

**解决**：把容器映射改成 `12424:11434`，并把 Dify / RagFlow 中所有模型 URL 统一改为
`http://host.docker.internal:12424`。

```yaml
ports:
  - "12424:11434"
```

> 排查思路：`netsh interface ipv4 show excludedportrange protocol=tcp` 可以查看系统保留段。

---

## 4. 端口冲突：MCP 服务起在 9000 上失败

**现象**：MCP 服务（默认 9000）启动后连不上。

**原因**：RagFlow 的 **MinIO** 已经占用 9000。

**解决**：把 MCP 服务改到 **9002**（`src/mcp_server.py` 末尾 `mcp.run(..., port=9002)`），
Dify 侧工具地址填 `http://host.docker.internal:9002/sse`。

> 同类问题：Dify 默认 80/443、RagFlow 默认 9380/9200 都可能与本机其他服务冲突，
> 建议统一规划端口后再部署。

---

## 5. Dify 接入 RagFlow 外部知识库报 403 / 连接失败

**现象**：在 Dify 填好外部知识库 API 后验证失败，返回 403 Forbidden。

**原因**：两个独立问题叠加——

1. **端点多写了一层**：Dify 会自己在端点后拼接 `/retrieval` 与 `/retrieval/health`，
   如果填成 `.../api/v1/dify/retrieval` 就会 404/403；
2. **SSRF 防护拦截内网地址**：Dify 默认把 `host.docker.internal`（解析为 `192.168.65.254`）判为内网并拒绝。

**解决**：

```bash
# 1) 端点只填到 /api/v1/dify，不要带 /retrieval
#    正确：http://host.docker.internal:50003/api/v1/dify
#    错误：http://host.docker.internal:50003/api/v1/dify/retrieval

# 2) 放行内网地址（F:\dify-1.17.0\docker\.env）
SSRF_PROXY_ALLOW_PRIVATE_IPS=192.168.65.254/32

# 3) 必须重建容器，restart 不会重新读取 .env
docker compose -p dify_docker up -d
```

---

## 6. 硅基流动报 `20015 No user query found in messages`

**现象**：把 LLM 节点切到硅基流动（OpenAI 兼容接口）后，模型调用报 20015。

**原因**：硅基流动**要求请求的 `messages` 中必须包含 `user` 角色**的消息；
而该节点的提示词只配了 `system`，Dify 组装出来的请求里没有 user。

**解决**：在 Dify LLM 节点的提示词中**新增一条 user 角色消息**，内容填 `{{#sys.query#}}`。
修改后 `messages` 结构变为 `['system', 'user']`，报错消失。

---

## 7. `Model does not exist`（云端模型填错 ID）

**现象**：添加硅基流动模型时报 `Model does not exist`。

**原因**：模型 ID 少了组织前缀。填了 `Qwen3.5-27B`，实际应为 `Qwen/Qwen3.5-27B`。

**解决**：模型 ID 必须与平台一致（含 `Qwen/`、`deepseek-ai/` 等组织前缀）。
可用下面的命令列出账号下所有可用模型 ID：

```bash
curl -H "Authorization: Bearer $SILICONFLOW_API_KEY" https://api.siliconflow.cn/v1/models
```

---

## 8. ⭐ 本地小模型无视引擎数据、编造棋局内容

**现象**：链路完全正常（引擎摘要里的"总半回合数 33、第 6 回合 Nf6→Qd7、第 10 回合 cxb5→Qb4+"都准确），
但 LLM 输出的报告里出现"总半回合数 16""第 6 回合象走动""建议王车易位"等**与数据完全不符**的内容。

**排查过程**：

1. 查数据库 `workflow_node_executions`，确认 `code_summary` 节点产出的引擎摘要**准确无误**；
2. 确认 LLM 节点的上下文已正确绑定摘要变量；
3. 实测本地 `qwen:7b` 推理速度约 33 tokens/s（GPU 已生效），排除"跑不动"；
4. 结论：**7B 级模型在"严格遵循给定数据、禁止编造"这类约束下能力不足**，会无视上下文自行生成。

**解决**：把 LLM 节点切换到更强的托管模型（本项目用 **Qwen/Qwen3.5-27B**），
并在提示词中硬性约束"只依据给定数据作答，数据未提供时写'数据未提供'"。切换后报告与引擎数据完全一致。

> **经验**：涉及"以客观数据为准、禁止自由发挥"的场景，模型规模是硬门槛，
> 不能靠调 prompt 完全弥补 7B 级模型的能力差距。

---

## 9. `docker compose restart` 改 `.env` 不生效

**现象**：改了 `docker/.env`（端口、SSRF 白名单等）后执行 `docker compose restart`，配置没有生效。

**原因**：`restart` 只是重启已有容器，**不会重新读取 `.env` 并重建容器**。

**解决**：用 `up -d` 重建：

```bash
docker compose -p dify_docker up -d            # 全部
docker compose -p dify_docker up -d --no-deps api worker   # 指定服务
```

---

## 10. 拉取镜像缓慢 / 超时

**现象**：`docker pull` 长时间卡住或超时。

**解决**：配置国内镜像加速源（Docker Desktop → Settings → Docker Engine）：

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1panel.live",
    "https://hub.rat.dev"
  ]
}
```

---

## 11. 本地内存吃紧导致 Docker 引擎不稳定

**现象**：同时跑 Dify（6 个容器）+ RagFlow（5 个容器）+ Ollama，在 16GB 内存的机器上，
Docker 引擎偶尔无响应（`docker ps` 空返回 / 500 错误），所有服务一起掉线。

**解决**：

1. 重启 Docker Desktop：结束所有 `docker*` 进程后重新启动，容器会随
   `restart: unless-stopped` 自动恢复（约需 1–2 分钟）；
2. 长期方案：按需启停服务（不用的容器 `docker compose stop`）、给 WSL2 限制内存
   （`~/.wslconfig` 里的 `memory=`），或把 Ollama 换成云端 API 以省下约 8GB 显存/内存压力。

---

## 12. 工作流调试建议

- **看链路是否走通**：Dify 应用的「日志」页能看到每个节点的输入/输出，比猜快得多；
- **看数据库更彻底**：`workflow_node_executions` 表保留了每次执行的节点状态与数据，
  可以直接确认"是模型编造"还是"上游数据本来就错"；
- **分级限流**：分析整盘棋很慢（33 半回合 @ depth 16 约数分钟），先在命令行用小 `--depth` 验证逻辑，
  再调大深度跑正式分析。
