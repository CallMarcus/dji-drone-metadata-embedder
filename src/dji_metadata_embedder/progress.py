"""Machine-readable progress events (``--progress jsonl``).

One JSON object per line on stdout; the contract lives in
docs/PROGRESS_JSONL.md and docs/progress_jsonl.schema.json. Additive changes
keep ``"v": 1`` (consumers ignore unknown fields); breaking changes bump it.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

_V = 1


class NullProgress:
    """No-op sink used when ``--progress`` is not set."""

    @property
    def active(self) -> bool:
        return False

    def start(self, command: str, total: int | None = None) -> None:
        pass

    def advance(self, current: int, total: int, item: str | None = None) -> None:
        pass

    def warning(self, message: str, item: str | None = None) -> None:
        pass

    def result(self, ok: bool, outputs: list[str], summary: dict[str, Any]) -> None:
        pass

    def error(self, message: str, item: str | None = None) -> None:
        pass


class JsonlProgress(NullProgress):
    """Emit one compact JSON event per line, flushed immediately."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream if stream is not None else sys.stdout

    @property
    def active(self) -> bool:
        return True

    def _emit(self, event: str, **fields: Any) -> None:
        payload: dict[str, Any] = {"v": _V, "event": event}
        # Optional fields are passed as None when absent; drop those only
        # (False / [] / {} are real values and must survive).
        payload.update({k: v for k, v in fields.items() if v is not None})
        self._stream.write(
            json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"
        )
        self._stream.flush()

    def start(self, command: str, total: int | None = None) -> None:
        self._emit("start", command=command, total=total)

    def advance(self, current: int, total: int, item: str | None = None) -> None:
        self._emit("progress", current=current, total=total, item=item)

    def warning(self, message: str, item: str | None = None) -> None:
        self._emit("warning", message=message, item=item)

    def result(self, ok: bool, outputs: list[str], summary: dict[str, Any]) -> None:
        self._emit("result", ok=ok, outputs=outputs, summary=summary)

    def error(self, message: str, item: str | None = None) -> None:
        self._emit("error", message=message, item=item)


def make_progress(mode: str | None) -> NullProgress:
    """Factory for the ``--progress`` option value (``'jsonl'`` or None)."""
    return JsonlProgress() if mode == "jsonl" else NullProgress()
