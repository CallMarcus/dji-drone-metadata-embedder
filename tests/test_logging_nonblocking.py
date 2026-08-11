"""Non-blocking logging for the long-lived server commands (#490).

The GUI launches ``dji-embed panoedit`` with stderr redirected to a pipe
it never reads. Once that pipe fills, a blocking log write freezes the
request thread that made it — and when the write sits inside the save
lock, every later save queues behind it forever. ``make_logging_nonblocking``
moves the actual handler I/O onto a sacrificial listener thread: request
threads only ever enqueue, so a wedged stderr can no longer stall a save.
"""
from __future__ import annotations

import logging
import threading
import time

from dji_metadata_embedder.utilities import make_logging_nonblocking


class _BlockingHandler(logging.Handler):
    """Stands in for a stderr pipe nobody reads: emit blocks until told."""

    def __init__(self) -> None:
        super().__init__()
        self.unblock = threading.Event()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.unblock.wait(timeout=10)
        self.records.append(record)


def _private_logger(name: str, handler: logging.Handler) -> logging.Logger:
    log = logging.getLogger(name)
    log.handlers = [handler]
    log.propagate = False
    log.setLevel(logging.INFO)
    return log


def _wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_blocked_handler_no_longer_blocks_the_logging_call():
    handler = _BlockingHandler()
    log = _private_logger("nonblocking-test-blocked", handler)
    listener = make_logging_nonblocking(log)
    assert listener is not None
    try:
        started = time.monotonic()
        log.warning("save finished")          # must return immediately
        assert time.monotonic() - started < 1.0
        assert handler.records == []          # handler is still blocked
        handler.unblock.set()
        assert _wait_for(lambda: len(handler.records) == 1)
        assert handler.records[0].getMessage() == "save finished"
    finally:
        handler.unblock.set()
        listener.stop()


def test_records_still_reach_the_original_handler():
    handler = _BlockingHandler()
    handler.unblock.set()                     # behaves like a normal handler
    log = _private_logger("nonblocking-test-passthrough", handler)
    listener = make_logging_nonblocking(log)
    assert listener is not None
    try:
        log.info("hello %s", "world")
        assert _wait_for(lambda: len(handler.records) == 1)
        assert handler.records[0].getMessage() == "hello world"
    finally:
        listener.stop()


def test_wrapping_twice_is_a_no_op():
    handler = _BlockingHandler()
    handler.unblock.set()
    log = _private_logger("nonblocking-test-idempotent", handler)
    listener = make_logging_nonblocking(log)
    assert listener is not None
    try:
        assert make_logging_nonblocking(log) is None
        assert len(log.handlers) == 1
    finally:
        listener.stop()


def test_rewrap_of_a_mixed_state_keeps_the_first_queue_wired():
    # If a handler is added after the first wrap, wrapping again must not
    # discard the first QueueHandler — that would silently orphan its
    # listener and cut off every handler behind it (#490 review).
    h1 = _BlockingHandler()
    h1.unblock.set()
    log = _private_logger("nonblocking-test-rewrap", h1)
    listener1 = make_logging_nonblocking(log)
    assert listener1 is not None
    h2 = _BlockingHandler()
    h2.unblock.set()
    log.addHandler(h2)
    listener2 = make_logging_nonblocking(log)
    assert listener2 is not None
    try:
        log.info("both please")
        assert _wait_for(lambda: len(h2.records) == 1)
        assert _wait_for(lambda: len(h1.records) == 1)
    finally:
        listener1.stop()
        listener2.stop()


def test_logger_without_handlers_is_left_alone():
    log = logging.getLogger("nonblocking-test-empty")
    log.handlers = []
    assert make_logging_nonblocking(log) is None
    assert log.handlers == []
