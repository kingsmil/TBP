"""Persist live-run artifacts: every billed model run leaves an inspectable log.

Each LiveRunLog writes two files under tests/e2e/logs/ (gitignored):
  <UTC-stamp>-<name>.jsonl  — one JSON object per record, machine-readable
  <UTC-stamp>-<name>.md     — human-readable summary of agent outputs
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).parent / "logs"


class LiveRunLog:
    def __init__(self, name: str):
        LOG_DIR.mkdir(exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.jsonl_path = LOG_DIR / f"{stamp}-{name}.jsonl"
        self.md_path = LOG_DIR / f"{stamp}-{name}.md"
        self._md: list[str] = [f"# Live run: {name}", f"_UTC {stamp}_", ""]

    def record(self, kind: str, **payload: Any) -> None:
        """Append one machine-readable record."""
        with self.jsonl_path.open("a") as f:
            f.write(json.dumps({"kind": kind, **payload}, default=str) + "\n")

    def section(self, title: str) -> None:
        self._md += [f"## {title}", ""]

    def line(self, text: str) -> None:
        self._md.append(text)

    def block(self, obj: Any) -> None:
        self._md += ["```json", json.dumps(obj, indent=2, default=str), "```", ""]

    def close(self) -> Path:
        self.md_path.write_text("\n".join(self._md) + "\n")
        return self.md_path
