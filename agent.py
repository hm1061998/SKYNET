#!/usr/bin/env python3
"""Skill Agent (Javis) — CLI.

    python agent.py                         # chế độ tương tác
    python agent.py "resize ảnh a.jpg về 800x600"   # chạy một tác vụ
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Config          # noqa: E402
from core.orchestrator import SkillAgent  # noqa: E402

_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
_C = {"reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m", "green": "\033[32m",
      "red": "\033[31m", "yellow": "\033[33m", "cyan": "\033[36m", "blue": "\033[34m",
      "mag": "\033[35m"}


def _paint(line: str) -> str:
    if not _USE_COLOR:
        return line
    rules = {"[✓]": "green", "[✗]": "red", "[!]": "yellow", "[+]": "cyan",
             "[>]": "blue", "[i]": "dim", "[~]": "mag", "[TASK]": "bold"}
    for k, col in rules.items():
        if line.startswith(k) or line.startswith("[TASK]"):
            return _C[col] + line + _C["reset"]
    return line


def _log(line: str):
    print(_paint(line))


def run_task(agent: SkillAgent, task: str):
    print()
    res = agent.execute_task(task, log=_log)
    print()
    return res


BANNER = r"""
   ╦╔═╗╦  ╦╦╔═╗   Skill Agent — AI tự sinh kỹ năng
   ║╠═╣╚╗╔╝║╚═╗   gõ tác vụ để chạy • 'quit' để thoát
  ╚╝╩ ╩ ╚╝ ╩╚═╝
"""


def interactive(agent: SkillAgent):
    print(BANNER)
    print(f"[cfg] {agent.config.describe()}")
    work = agent.config.resolve("work")
    if not work.ready:
        print(_paint("[!] Model 'work' chưa có API key → không sinh được skill mới. "
                     "Điền key vào config.json hoặc đặt \"provider\": \"mock\" để chạy thử."))
    print()
    while True:
        try:
            task = input("\033[36m> \033[0m" if _USE_COLOR else "> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nTạm biệt 👋")
            return
        if not task:
            continue
        if task.lower() in ("quit", "exit", "thoat", "thoát", ":q"):
            print("Tạm biệt 👋")
            return
        try:
            run_task(agent, task)
        except Exception as e:
            print(_paint(f"[✗] Lỗi: {e}"))


def main():
    agent = SkillAgent(Config.load())
    if len(sys.argv) > 1:
        run_task(agent, " ".join(sys.argv[1:]))
    else:
        interactive(agent)


if __name__ == "__main__":
    main()
