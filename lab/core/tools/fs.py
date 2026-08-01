"""Sandboxed file access for workflows that read/write artifacts.

Both read AND write are guarded: an out-of-sandbox path returns a recoverable
``REJECTED: ...`` string rather than raising, so a repair agent can react to it
instead of the run crashing. (This is the bug we found and fixed in the mundiir
repair loop, avoided here from the start.)
"""

from __future__ import annotations

import os
from pathlib import Path


class PathNotAllowed(Exception):
    pass


class Sandbox:
    def __init__(self, roots: list[str], base: str | None = None) -> None:
        self.base = Path(base or os.getcwd()).resolve()
        self.roots = [(self.base / r).resolve() for r in roots]

    def _resolve(self, path: str) -> Path:
        p = (self.base / path).resolve()
        for root in self.roots:
            if p == root or str(p).startswith(str(root) + os.sep):
                return p
        allowed = ", ".join(str(r.relative_to(self.base)) for r in self.roots)
        raise PathNotAllowed(f"{path!r} is outside the sandbox; allowed: {allowed}")

    def read_file(self, path: str) -> str:
        try:
            p = self._resolve(path)
        except PathNotAllowed as exc:
            return f"REJECTED: {exc}"
        if not p.is_file():
            return f"[missing] {path}"
        return p.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        try:
            p = self._resolve(path)
        except PathNotAllowed as exc:
            return f"REJECTED: {exc}"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"wrote {path}"
