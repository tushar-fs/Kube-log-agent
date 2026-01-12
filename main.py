#!/usr/bin/env python3
import sys
import time
import argparse
import threading

from k8s import load_kube_client, find_crashing_pods, fetch_logs
from vector_db import index_runbooks, query_runbooks
from agent import query_llm


# ── terminal helpers ──────────────────────────────────────────────────────────

BOLD  = "\033[1m"
RED   = "\033[1;31m"
GREEN = "\033[1;32m"
YELLOW = "\033[1;33m"
CYAN  = "\033[1;36m"
RESET = "\033[0m"

def _header(text: str):
    width = 60
    print(f"\n{CYAN}{'─' * width}{RESET}")
    print(f"{BOLD}  {text}{RESET}")
    print(f"{CYAN}{'─' * width}{RESET}")

def _ok(text: str):
    print(f"{GREEN}✔{RESET}  {text}")

def _info(text: str):
    print(f"   {text}")

def _warn(text: str):
    print(f"{YELLOW}⚠{RESET}  {text}")


class Spinner:
    """Minimal spinner so the user knows we're not hung."""
    _frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str):
        self.message = message
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        i = 0
        while not self._stop_event.is_set():
            frame = self._frames[i % len(self._frames)]
            print(f"\r{CYAN}{frame}{RESET}  {self.message}", end="", flush=True)
            time.sleep(0.1)
            i += 1

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop_event.set()
        self._thread.join()
        print("\r" + " " * (len(self.message) + 6) + "\r", end="", flush=True)


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_debug(args):
    namespace = args.namespace

    _header(f"kube-log-agent  ·  namespace: {namespace}")

    # 1. find crashing pods
    with Spinner("Scanning pods for crash states..."):
        v1 = load_kube_client()
        crashing = find_crashing_pods(v1, namespace)

    if not crashing:
        _ok(f"No crashing pods found in '{namespace}'.")
        return

    print(f"\n  Found {BOLD}{len(crashing)}{RESET} crashing pod(s):\n")
    for i, p in enumerate(crashing, 1):
        print(f"  {BOLD}[{i}]{RESET} {p['pod']}  "
              f"({RED}{p['reason']}{RESET}, restarts: {p['restart_count']})")

    # if there are multiple, let the user pick or default to the worst offender
    if len(crashing) > 1 and not args.all:
        target = sorted(crashing, key=lambda x: x["restart_count"], reverse=True)[0]
        _warn(f"Targeting pod with most restarts: {BOLD}{target['pod']}{RESET}. "
              f"Use --all to process all.")
    else:
        target = crashing[0] if not args.all else None

    pods_to_process = crashing if args.all else [target]

    # 2. index runbooks once upfront
    with Spinner("Checking runbook index..."):
        db = index_runbooks(force=args.reindex)

    for pod_info in pods_to_process:
        pod_name  = pod_info["pod"]
        container = pod_info["container"]

        _header(f"Analyzing: {pod_name}")

        with Spinner(f"Fetching logs from {pod_name}/{container}..."):
            logs = fetch_logs(v1, pod_name, namespace, container)

        if not logs.strip():
            _warn(f"No logs available for {pod_name}. Skipping.")
            continue

        _ok(f"Fetched {len(logs.splitlines())} lines of logs.")

        with Spinner("Querying runbook index..."):
            context_chunks = query_runbooks(db, logs)

        if context_chunks:
            _ok(f"Found {len(context_chunks)} relevant runbook chunk(s).")
        else:
            _info("No runbook context found — proceeding without it.")

        with Spinner(f"Asking {BOLD}llama3{RESET} for root cause..."):
            summary = query_llm(pod_name, logs, context_chunks)

        print(f"\n{BOLD}{'─' * 60}{RESET}")
        print(summary)
        print(f"{BOLD}{'─' * 60}{RESET}\n")


def cmd_index(_args):
    """Explicit re-index command for when you've updated your runbooks."""
    print("Re-indexing runbooks...")
    db = index_runbooks(force=True)
    _ok("Runbook index updated.")


# ── entrypoint ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="kube-log-agent",
        description="Local Kubernetes crash debugger powered by a local LLM.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    debug_p = sub.add_parser("debug", help="Find crashing pods and generate a root-cause summary.")
    debug_p.add_argument("-n", "--namespace", default="default",
                         help="Kubernetes namespace to scan (default: default)")
    debug_p.add_argument("--all", action="store_true",
                         help="Analyze all crashing pods instead of just the worst offender.")
    debug_p.add_argument("--reindex", action="store_true",
                         help="Force re-embedding of runbooks before querying.")
    debug_p.set_defaults(func=cmd_debug)

    index_p = sub.add_parser("index", help="Re-index the runbooks directory.")
    index_p.set_defaults(func=cmd_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
