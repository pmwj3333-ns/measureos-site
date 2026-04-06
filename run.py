"""ローカル開発用: python3 run.py のみで起動すること（uvicorn 直起動は非推奨）。

- 起動前に TCP 8002 の既存リスナーを終了（ポート競合・古いプロセス対策）
- MEASUREOS_ALLOW_TEST_CLOCK が未設定なら "1"（既にある場合は上書きしない）

本番では app.main:app を直接起動し、このスクリプトは使わない。
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys

import uvicorn

DEV_PORT = 8002


def _kill_tcp_listeners_on_port(port: int) -> None:
    """Mac/Linux: lsof で LISTEN 中の PID を SIGKILL（自プロセスは除外）。"""
    try:
        proc = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        print(
            "run.py: lsof が見つかりません。ポート掃除をスキップします。",
            file=sys.stderr,
        )
        return
    except subprocess.TimeoutExpired:
        print("run.py: lsof がタイムアウトしました。", file=sys.stderr)
        return

    if proc.returncode != 0 or not proc.stdout.strip():
        return

    mypid = os.getpid()
    for pid_str in proc.stdout.strip().split():
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        if pid == mypid:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            print(f"run.py: PID {pid} を終了できませんでした（権限）", file=sys.stderr)


if __name__ == "__main__":
    _kill_tcp_listeners_on_port(DEV_PORT)

    if "MEASUREOS_ALLOW_TEST_CLOCK" not in os.environ:
        os.environ["MEASUREOS_ALLOW_TEST_CLOCK"] = "1"

    uvicorn.run("app.main:app", host="127.0.0.1", port=DEV_PORT, reload=True)
