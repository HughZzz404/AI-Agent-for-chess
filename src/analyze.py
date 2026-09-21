"""Chess game analysis: per-move eval, win%-loss, classification.

Usage:
    python analyze.py <pgn_or_fen> --depth 16 --multipv 3

Evaluates each position before/after a move with Stockfish, converts the
engine's centipawn/mate score to a win-probability (Lichess formula), and
reports the *win%-loss* each move incurred for its side. Win% loss is bounded
(0..100) and mate-safe, unlike raw centipawn loss which explodes to ~100000
on mate scores and misclassifies terminal positions. Outputs JSON plus the
top `--topn` divergences.
"""

import argparse
import io
import json
import math
import os
import sys

import chess
import chess.engine
import chess.pgn


def default_engine_path():
    """Locate the Stockfish binary.

    Priority: $STOCKFISH_PATH  ->  <repo>/engine/stockfish/<platform binary>.
    Fetch it with:  python scripts/download_stockfish.py
    """
    env = os.environ.get("STOCKFISH_PATH")
    if env and os.path.exists(env):
        return env
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if sys.platform.startswith("win"):
        name = "stockfish-windows-x86-64-avx2.exe"
    elif sys.platform == "darwin":
        name = "stockfish-macos-m1-apple-silicon"
    else:
        name = "stockfish-ubuntu-x86-64-avx2"
    return os.path.join(root, "engine", "stockfish", name)


# --- engine + scoring -----------------------------------------------------

def _cp_to_winpct(cp):
    """Lichess win-probability formula, input cp on white POV. Returns 0..100."""
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def white_winpct_from_pov(pov, depth_hint):
    """Convert a score value (white perspective) to a bounded win% 0..100.

    In python-chess 1.11.2, PovScore.pov(turn) returns an `int` (centipawns)
    or a `chess.engine.Mate`. Handle both. Mate: white mates -> ~100, else ~0.
    """
    # Mate object
    if hasattr(pov, "mate") and not isinstance(pov, int):
        try:
            if pov.is_mate():
                return 100.0 if pov.mate() > 0 else 0.0
        except Exception:
            pass
    # int (plain centipawns) or anything with .score()
    if isinstance(pov, int):
        cp = max(-2000, min(2000, pov))
    else:
        try:
            if pov.is_mate():
                return 100.0 if pov.mate() > 0 else 0.0
        except Exception:
            pass
        sc = pov.score()
        cp = sc if sc is not None else 50
        cp = max(-2000, min(2000, cp))
    return _cp_to_winpct(cp)


def best_eval(engine, board, depth, multipv=1):
    """Return (win_pct_for_white, eval_cp_for_white, best_san).

    best_san is the engine's top continuation in SAN for this position.
    """
    info_list = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
    info = info_list[0] if isinstance(info_list, list) else info_list
    pv = info.get("pv", [])
    best_san = board.san(pv[0]) if pv else "-"
    score = info.get("score", chess.engine.PovScore(0, chess.WHITE))
    pov = score.pov(chess.WHITE)  # int (centipawns) or chess.engine.Mate
    winpct = white_winpct_from_pov(pov, depth)
    if isinstance(pov, int):
        cp = pov
    else:
        m = pov.mate()
        cp = 100000 if (m is not None and m > 0) else -100000 if (m is not None and m < 0) else 0
    return winpct, cp, best_san


def classify(win_loss):
    """Map win%-loss (0..100) to a human label.

    Thresholds roughly match Lichess's eval%-drop buckets.
    """
    if win_loss <= 2.0:
        return "best/exact"
    if win_loss <= 5.0:
        return "good"
    if win_loss <= 10.0:
        return "inaccuracy"
    if win_loss <= 20.0:
        return "mistake"
    return "blunder"


# --- game stepping --------------------------------------------------------

def step_game(pgn_text, engine, depth, multipv, topn):
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("No game found in PGN")
    board = game.board()
    moves = list(game.mainline_moves())
    report = []
    for i, mover_move in enumerate(moves):
        turn_was_white = board.turn == chess.WHITE
        winpct_before, cp_before, best_san = best_eval(engine, board, depth, multipv)
        san = board.san(mover_move)
        board.push(mover_move)
        # After the move, the game may be over -> don't re-search a dead board.
        if board.is_checkmate():
            # the mover just mated the opponent => mover's win% becomes 100
            winpct_after = 100.0 if turn_was_white else 0.0
            cp_after = 100000 if turn_was_white else -100000
        elif board.is_game_over():
            # stalemate / draw-by-rule on this move
            winpct_after = 50.0
            cp_after = 0
        else:
            winpct_after, cp_after, _ = best_eval(engine, board, depth, multipv=1)

        # win%-loss in the MOVER's interest: how much did their win% drop?
        # mover's win% = winpct_for_white if they're white else (100 - white%)
        mover_before = (winpct_before if turn_was_white else 100 - winpct_before)
        mover_after = (winpct_after if turn_was_white else 100 - winpct_after)
        loss = max(0.0, mover_before - mover_after)  # clamp negatives (search noise)
        if loss < 0.3:
            loss = 0.0

        report.append({
            "move_no": i // 2 + 1,
            "move": san,
            "side": "white" if turn_was_white else "black",
            "winpct_before": round(winpct_before, 1),
            "winpct_after": round(winpct_after, 1),
            "eval_before_cp": cp_before,
            "eval_after_cp": cp_after,
            "best_before": best_san,
            "win_loss": round(loss, 1),
            "classification": classify(loss),
        })
    return report, board


# --- main ----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="PGN text or FEN, or a path to a .pgn/.fen file")
    ap.add_argument("--engine", default=default_engine_path(),
                    help="path to the Stockfish binary (default: $STOCKFISH_PATH or engine/stockfish/...)")
    ap.add_argument("--depth", type=int, default=16)
    ap.add_argument("--multipv", type=int, default=3)
    ap.add_argument("--topn", type=int, default=5)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    raw = args.input
    if raw.endswith(".pgn") or raw.endswith(".fen"):
        with open(raw, encoding="utf-8") as f:
            raw = f.read()

    with chess.engine.SimpleEngine.popen_uci(args.engine) as engine:
        report, board = step_game(raw, engine, args.depth, args.multipv, args.topn)

    divergences = sorted(report, key=lambda r: r["win_loss"], reverse=True)[: args.topn]

    result = {
        "engine": args.engine,
        "depth": args.depth,
        "multipv": args.multipv,
        "num_moves": len(report),
        "final_fen": board.fen(),
        "top_divergences": divergences,
        "moves": report,
    }

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"wrote {args.json_out}")
    print(out[:4000])


if __name__ == "__main__":
    main()
