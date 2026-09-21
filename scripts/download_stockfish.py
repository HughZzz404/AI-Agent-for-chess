#!/usr/bin/env python3
"""下载对应平台的 Stockfish 官方二进制到 engine/stockfish/。

用法:
    python scripts/download_stockfish.py
    python scripts/download_stockfish.py --asset stockfish-windows-x86-64.zip
    python scripts/download_stockfish.py --proxy http://127.0.0.1:7890

说明:
    - 二进制不入库（约 200MB，含 NNUE 神经网络权重文件）。
    - 下载源为 official-stockfish/Stockfish 的 GitHub Release。
    - 若网络受限，可手动下载后解压，把可执行文件与 *.nnue 放到 engine/stockfish/，
      并设置环境变量 STOCKFISH_PATH 指向可执行文件。
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEST = REPO_ROOT / "engine" / "stockfish"
BASE_URL = "https://github.com/official-stockfish/Stockfish/releases/latest/download"

# 平台 -> (压缩包后缀, 包内的可执行文件名)
ASSETS = {
    "windows": ("stockfish-windows-x86-64-avx2.zip", "stockfish-windows-x86-64-avx2.exe"),
    "linux": ("stockfish-ubuntu-x86-64-avx2.tar", "stockfish-ubuntu-x86-64-avx2"),
    "darwin-arm": ("stockfish-macos-m1-apple-silicon.tar", "stockfish-macos-m1-apple-silicon"),
    "darwin-x86": ("stockfish-macos-x86-64-avx2.tar", "stockfish-macos-x86-64-avx2"),
}


def pick_asset() -> tuple[str, str]:
    """根据当前平台选择 release 资源与可执行文件名。"""
    system = platform.system().lower()
    if system.startswith("win"):
        return ASSETS["windows"]
    if system == "darwin":
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            return ASSETS["darwin-arm"]
        return ASSETS["darwin-x86"]
    return ASSETS["linux"]


def download(url: str, dest: Path, proxy: str | None) -> None:
    """下载 url 到 dest，带简单进度输出。"""
    if proxy:
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        urllib.request.install_opener(urllib.request.build_opener(handler))

    print(f"↓ 下载 {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "stockfish-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as fh:
            while chunk := resp.read(1 << 20):
                fh.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 // total
                    print(f"\r  {done / 1e6:7.1f} / {total / 1e6:.1f} MB ({pct}%)", end="")
                else:
                    print(f"\r  {done / 1e6:7.1f} MB", end="")
    print()


def extract(archive: Path, dest: Path) -> None:
    """解压并把可执行文件与 NNUE 权重平铺到 dest。"""
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(tmp_path)
        else:
            with tarfile.open(archive) as tf:
                tf.extractall(tmp_path)

        # release 包结构一般是 stockfish/<文件...>
        src_dir = tmp_path / "stockfish"
        if not src_dir.is_dir():
            sub = [d for d in tmp_path.iterdir() if d.is_dir()]
            src_dir = sub[0] if sub else tmp_path

        copied = 0
        for item in src_dir.iterdir():
            if item.is_file() and (item.suffix in (".exe", ".nnue") or item.name.startswith("stockfish")):
                shutil.copy2(item, dest / item.name)
                copied += 1
        print(f"✓ 已复制 {copied} 个文件到 {dest}")


def main() -> int:
    ap = argparse.ArgumentParser(description="下载 Stockfish 官方二进制")
    ap.add_argument("--asset", help="手动指定 release 资源名（覆盖自动识别）")
    ap.add_argument("--proxy", help="HTTP 代理，例如 http://127.0.0.1:7890")
    args = ap.parse_args()

    asset, exe = pick_asset()
    if args.asset:
        asset = args.asset
        exe = next((e for a, e in ASSETS.values() if a == asset), exe)

    print(f"平台: {platform.system()} {platform.machine()}")
    print(f"资源: {asset}")

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / asset
        try:
            download(f"{BASE_URL}/{asset}", archive, args.proxy)
        except Exception as exc:  # noqa: BLE001
            print(f"\n✗ 下载失败: {exc}", file=sys.stderr)
            print("  可手动下载 https://stockfishchess.org/download/ 后，", file=sys.stderr)
            print(f"  把可执行文件与 *.nnue 放入 {DEST}，或设置 STOCKFISH_PATH。", file=sys.stderr)
            return 1
        extract(archive, DEST)

    target = DEST / exe
    if not target.exists():
        # 退而求其次：找目录里第一个 stockfish 可执行文件
        cands = [p for p in DEST.iterdir() if p.name.startswith("stockfish") and p.suffix != ".nnue"]
        if cands:
            target = cands[0]
        else:
            print(f"✗ 未找到可执行文件，请检查 {DEST}", file=sys.stderr)
            return 1

    if os.name != "nt":
        target.chmod(0o755)

    print(f"\n✓ 完成: {target}")
    print(f"  试运行: python src/analyze.py examples/ruy_lopez_short.pgn --depth 8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
