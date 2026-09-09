#!/usr/bin/env python3
"""CLI for the first AI agent — start here, then iterate.

Usage:
  python -m value_scanner.agent.cli
  python -m value_scanner.agent.cli --once "σκαν"
  python -m value_scanner.agent.cli --provider demo --once "καβά"
  AGENT_LLM=openai OPENAI_API_KEY=... python -m value_scanner.agent.cli
"""

from __future__ import annotations

import argparse
import sys

from value_scanner.agent.llm import detect_provider
from value_scanner.agent.loop import Agent


def _print_trace(trace: list, verbose: bool) -> None:
    if not verbose or not trace:
        return
    print("\n--- heartbeat ---", file=sys.stderr)
    for item in trace:
        print(
            f"  step {item['step']}: {item['tool']}({item['arguments']})",
            file=sys.stderr,
        )
    print("--- /heartbeat ---\n", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Novibet Value Agent (model→tool→result→model)")
    parser.add_argument("--provider", choices=["demo", "openai", "anthropic"], default=None)
    parser.add_argument("--once", metavar="TEXT", help="Run one turn and exit")
    parser.add_argument("--no-memory", action="store_true", help="Do not persist conversation JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show tool heartbeat on stderr")
    parser.add_argument("--max-steps", type=int, default=8)
    args = parser.parse_args(argv)

    provider = args.provider or detect_provider()
    agent = Agent(provider=provider, max_steps=args.max_steps, persist_memory=not args.no_memory)

    if args.once is not None:
        result = agent.run(args.once)
        _print_trace(result.tool_trace, verbose=True)
        print(result.reply)
        return 0

    print(f"Value Agent ready | provider={provider}")
    print("Εντολές: μήνυμα · /reset · /trace · /quit")
    print("Παραδείγματα: «σκαν» · «#5 2.03» · «καβά»\n")

    show_trace = args.verbose
    while True:
        try:
            user = input("εσύ> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user:
            continue
        low = user.lower()
        if low in {"/quit", "/exit", "quit", "exit"}:
            return 0
        if low == "/reset":
            agent.memory.clear_dialogue()
            from value_scanner.agent.loop import SYSTEM_PROMPT

            agent.memory.add_system(SYSTEM_PROMPT)
            print("(μνήμη καθαρίστηκε)")
            continue
        if low == "/trace":
            show_trace = not show_trace
            print(f"(trace {'on' if show_trace else 'off'})")
            continue

        result = agent.run(user)
        _print_trace(result.tool_trace, show_trace)
        print(f"\nagent>\n{result.reply}\n")


if __name__ == "__main__":
    raise SystemExit(main())
