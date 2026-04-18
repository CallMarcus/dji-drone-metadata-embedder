"""In-process job registry for long-running UI tasks.

Each job runs a subprocess, streams stdout lines as ``log`` events, and
exposes a blocking subscription iterator that SSE handlers drain.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Iterator

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
_HEARTBEAT_TIMEOUT = 15.0


@dataclass
class Job:
    id: str
    kind: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    events: list[dict] = field(default_factory=list)
    _cond: threading.Condition = field(default_factory=threading.Condition)
    _cancel: threading.Event = field(default_factory=threading.Event)
    _proc: subprocess.Popen | None = None
    _thread: threading.Thread | None = None

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "event_count": len(self.events),
        }

    def append(self, event: dict) -> None:
        with self._cond:
            self.events.append(event)
            self._cond.notify_all()

    def set_status(self, status: str) -> None:
        with self._cond:
            self.status = status
            if status in TERMINAL_STATUSES and self.finished_at is None:
                self.finished_at = time.time()
            self._cond.notify_all()

    def subscribe(self, start: int = 0) -> Iterator[dict]:
        """Yield events from ``start`` onward, blocking until terminal."""
        seq = start
        while True:
            with self._cond:
                while (
                    len(self.events) <= seq
                    and self.status not in TERMINAL_STATUSES
                ):
                    if not self._cond.wait(timeout=_HEARTBEAT_TIMEOUT):
                        yield {"type": "ping", "t": time.time()}
                batch = self.events[seq:]
                seq = len(self.events)
                terminal = self.status in TERMINAL_STATUSES
                final_status = self.status
                final_error = self.error
            for ev in batch:
                yield ev
            if terminal:
                yield {"type": "status", "status": final_status, "error": final_error}
                return

    def request_cancel(self) -> None:
        self._cancel.set()
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError as exc:  # pragma: no cover - defensive
                logger.warning("proc.terminate failed for job %s: %s", self.id, exc)
        self.append(
            {"type": "log", "level": "warn", "msg": "Cancellation requested."}
        )


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, kind: str) -> Job:
        job = Job(id=uuid.uuid4().hex, kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())


_registry = JobRegistry()


def registry() -> JobRegistry:
    return _registry


def run_subprocess_job(job: Job, cmd: list[str]) -> None:
    """Start ``cmd`` under ``job`` in a background daemon thread."""

    def _target() -> None:
        job.started_at = time.time()
        job.set_status("running")
        job.append(
            {"type": "log", "level": "info", "msg": "$ " + " ".join(cmd)}
        )
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            job._proc = proc
            assert proc.stdout is not None
            for raw in proc.stdout:
                if job._cancel.is_set():
                    break
                line = raw.rstrip("\r\n")
                if line:
                    job.append({"type": "log", "level": "info", "msg": line})
            rc = proc.wait()
            if job._cancel.is_set():
                job.set_status("cancelled")
            elif rc == 0:
                job.set_status("succeeded")
            else:
                job.error = f"exit code {rc}"
                job.set_status("failed")
        except Exception as exc:
            job.error = str(exc)
            job.append({"type": "log", "level": "err", "msg": f"Error: {exc}"})
            job.set_status("failed")

    thread = threading.Thread(target=_target, daemon=True, name=f"job-{job.id[:8]}")
    job._thread = thread
    thread.start()
