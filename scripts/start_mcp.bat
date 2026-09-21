@echo off
setlocal EnableExtensions
REM ============================================================
REM  Stockfish MCP Server 启动脚本（SSE，默认端口 9002）
REM  崩溃后自动重启。本脚本位于 scripts\ ，会自动切到仓库根目录。
REM ============================================================
title Stockfish MCP Server

cd /d "%~dp0.." || exit /b 1
if not defined MCP_PORT set "MCP_PORT=9002"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

:restart
echo [%date% %time%] Starting Stockfish MCP on port %MCP_PORT% ...

REM 结束占用 MCP 端口的旧进程
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%MCP_PORT% .*LISTENING"') do (
  echo [%date% %time%] Stopping previous listener on port %MCP_PORT%: PID %%P
  taskkill /F /PID %%P >nul 2>&1
)
timeout /t 2 /nobreak >nul

"%PY%" "src\mcp_server.py"
echo [%date% %time%] MCP exited. Restarting in 3 seconds...
timeout /t 3 /nobreak >nul
goto restart
