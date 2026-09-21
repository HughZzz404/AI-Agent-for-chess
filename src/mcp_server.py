"""Stockfish MCP server (module 5 pattern).

Exposes Stockfish-backed tools to Dify via FastMCP over SSE (:9000).

Tools:
    analyze_game(pgn)        -> per-move eval + win%-loss + classification + top divergences
    best_moves(fen, depth)   -> engine top lines (MultiPV) for a position
    evaluate_position(fen)   -> winPct/cp for a single position (used in chat follow-ups)

Reuses the analysis core from analyze.py. Holds ONE long-lived engine to avoid
reloading the 125MiB NNUE net on every call.
"""

import json
import os
import sys

from fastmcp import FastMCP
import chess
import chess.engine
import chess.pgn

# Reuse analysis core (best_eval, classify, step_game) from analyze.py
import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_ANALYZE = os.path.join(_HERE, "analyze.py")
_spec = importlib.util.spec_from_file_location("analyze_core", _ANALYZE)
analyze_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analyze_core)


def _default_engine_name():
    """Stockfish release binary name for the current platform."""
    if sys.platform.startswith("win"):
        return "stockfish-windows-x86-64-avx2.exe"
    if sys.platform == "darwin":
        return "stockfish-macos-m1-apple-silicon"
    return "stockfish-ubuntu-x86-64-avx2"


def _engine_path():
    """Resolve the Stockfish binary.

    Priority: $STOCKFISH_PATH  ->  <repo>/engine/stockfish/<platform binary>
    Run `python scripts/download_stockfish.py` to fetch the binary.
    """
    env = os.environ.get("STOCKFISH_PATH")
    if env and os.path.exists(env):
        return env
    return os.path.join(_ROOT, "engine", "stockfish", _default_engine_name())


_ENGINE_PATH = _engine_path()
DEFAULT_DEPTH = 16

_engine = None  # lazily opened, kept alive for server lifetime


def _get_engine():
    global _engine
    if _engine is None:
        _engine = chess.engine.SimpleEngine.popen_uci(_ENGINE_PATH)
        # moderate hash for a laptop; avoid huge RAM
        _engine.configure({"Threads": 1, "Hash": 64})
    return _engine


mcp = FastMCP(name="Stockfish Chess Analyzer")


@mcp.tool(name="analyze_game",
          description=(
              "Analyze a full chess game and report per-move evaluation, win%-loss, "
              "classification (best/exact, good, inaccuracy, mistake, blunder), the "
              "engine's best alternative move at each step, and the top divergences. "
              "Input is a PGN string (moves in Standard Algebraic Notation). "
              "Call this when the user supplies or uploads a game record (棋谱/对局)."
          ))
def analyze_game(pgn_text: str, depth: int = DEFAULT_DEPTH, topn: int = 5,
                 multipv: int = 3) -> dict:
    """Analyze a whole game given as a PGN string. Returns a JSON-ready dict."""
    engine = _get_engine()
    report, board = analyze_core.step_game(pgn_text, engine, depth, multipv, topn)
    divergences = sorted(report, key=lambda r: r["win_loss"], reverse=True)[:topn]
    return {
        "num_moves": len(report),
        "final_fen": board.fen(),
        "result": game_result(pgn_text),
        "top_divergences": divergences,
        "moves": report,
    }


@mcp.tool(name="best_moves",
          description=(
              "For a single position (FEN string), return the engine's top candidate "
              "moves with win% and centipawn eval (MultiPV). Use when the user asks "
              "'what should I play here?' or wants alternatives in a position."
          ))
def best_moves(fen: str, depth: int = DEFAULT_DEPTH, multipv: int = 3) -> dict:
    """Return the top `multipv` engine lines for a FEN position."""
    engine = _get_engine()
    board = chess.Board(fen)
    info_list = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
    infos = info_list if isinstance(info_list, list) else [info_list]
    lines = []
    for info in infos:
        pv = info.get("pv", [])
        san = board.san(pv[0]) if pv else "-"
        # python-chess >= 1.11: PovScore.pov() returns an int (centipawns) or Mate,
        # NOT a Score object - calling .score()/.pov() on it would raise AttributeError.
        pov = info.get("score", chess.engine.PovScore(0, chess.WHITE)).pov(chess.WHITE)
        winpct = analyze_core.white_winpct_from_pov(pov, depth)
        if isinstance(pov, int):
            cp = pov
        else:
            m = pov.mate()
            cp = 100000 if (m is not None and m > 0) else -100000 if (m is not None and m < 0) else 0
        lines.append({"move": san, "winpct": round(winpct, 1), "eval_cp": cp,
                      "pv": " ".join(board.san(m) for m in pv[:8])})
    return {"fen": fen, "depth": depth, "lines": lines}


@mcp.tool(name="evaluate_position",
          description=(
              "Evaluate a single position (FEN) and return the win% for white. Use as a "
              "quick score check, e.g. to answer 'who stands better right now?'"
          ))
def evaluate_position(fen: str, depth: int = 16) -> dict:
    """Return winPct/cp for a FEN position."""
    engine = _get_engine()
    board = chess.Board(fen)
    winpct, cp, best = analyze_core.best_eval(engine, board, depth, multipv=1)
    return {"fen": fen, "winpct_white": round(winpct, 1), "eval_cp": cp,
            "best_move": best}


def game_result(pgn_text: str) -> str:
    """Parse the PGN header Result, defaulting to '' if absent."""
    try:
        game = chess.pgn.read_game(io_string(pgn_text))
        return game.headers.get("Result", "") if game else ""
    except Exception:
        return ""


def io_string(s):
    import io
    return io.StringIO(s)


if __name__ == "__main__":
    # 端口 9000 被 ragflow minio 占用，改用 9002（host 端口；容器内仍 0.0.0.0）
    mcp.run(transport="sse", host="0.0.0.0", port=9002)
