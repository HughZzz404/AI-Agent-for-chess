#!/usr/bin/env bash
# ============================================================
#  Stockfish MCP Server 启动脚本（SSE，默认端口 9002）
#  崩溃后自动重启。本脚本位于 scripts/ ，会自动切到仓库根目录。
# ============================================================
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
PORT="${MCP_PORT:-9002}"

stop_old_listener() {
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "[$(date '+%F %T')] Stopping previous listener on port $PORT: $pids"
      # shellcheck disable=SC2086
      kill -9 $pids 2>/dev/null || true
    fi
  fi
}

PY="python3"
[ -x ".venv/bin/python" ] && PY=".venv/bin/python"

while true; do
  echo "[$(date '+%F %T')] Starting Stockfish MCP on port $PORT ..."
  stop_old_listener
  sleep 1
  "$PY" src/mcp_server.py
  echo "[$(date '+%F %T')] MCP exited. Restarting in 3 seconds..."
  sleep 3
done
