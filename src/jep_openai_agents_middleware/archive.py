"""Append-only JEP archive and replay verification runtime."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
from typing import Any, Iterable, Mapping
from uuid import uuid4

from .events import JEPEvent


@dataclass(frozen=True)
class ReplayReport:
    """Result of deterministic archive replay verification."""

    valid: bool
    checked_events: int
    errors: tuple[str, ...] = ()
    terminal_hash: str | None = None


class AppendOnlyArchive:
    """JSONL append-only event archive.

    The archive never rewrites existing lines. Each appended event receives the
    next sequence number and previous event hash before being flushed to disk.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._lock = threading.Lock()

    def read_events(self) -> list[JEPEvent]:
        events: list[JEPEvent] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                events.append(JEPEvent.from_dict(json.loads(line)))
            except Exception as exc:  # pragma: no cover - defensive corruption reporting
                raise ValueError(f"Invalid archive line {line_number}: {exc}") from exc
        return events

    def append(self, event_type: str, run_id: str, payload: Mapping[str, Any]) -> JEPEvent:
        with self._lock:
            existing = self.read_events()
            prev_hash = existing[-1].hash if existing else None
            event = JEPEvent(
                event_type=event_type,
                run_id=run_id,
                sequence=len(existing) + 1,
                prev_hash=prev_hash,
                payload=payload,
            ).with_hash()
            with self.path.open("a", encoding="utf-8") as archive_file:
                archive_file.write(event.to_json_line())
                archive_file.flush()
            return event


class VerificationRuntime:
    """Creates JEP events and verifies deterministic replay chains."""

    def __init__(self, archive: AppendOnlyArchive | str | Path = "jep-archive.jsonl", run_id: str | None = None):
        self.archive = archive if isinstance(archive, AppendOnlyArchive) else AppendOnlyArchive(archive)
        self.run_id = run_id or uuid4().hex

    def emit(self, event_type: str, payload: Mapping[str, Any]) -> JEPEvent:
        return self.archive.append(event_type=event_type, run_id=self.run_id, payload=payload)

    def judgment(self, subject: str, payload: Mapping[str, Any]) -> JEPEvent:
        return self.emit("judgment", {"subject": subject, **payload})

    def delegation(self, payload: Mapping[str, Any]) -> JEPEvent:
        return self.emit("delegation", payload)

    def termination(self, payload: Mapping[str, Any]) -> JEPEvent:
        return self.emit("termination", payload)

    def verify(self, events: Iterable[JEPEvent] | None = None) -> ReplayReport:
        checked = 0
        errors: list[str] = []
        previous_hash: str | None = None
        terminal_hash: str | None = None
        for expected_sequence, event in enumerate(events or self.archive.read_events(), start=1):
            checked += 1
            if event.sequence != expected_sequence:
                errors.append(f"sequence mismatch at index {expected_sequence}: got {event.sequence}")
            if event.prev_hash != previous_hash:
                errors.append(f"prev_hash mismatch at sequence {event.sequence}")
            recomputed = event.with_hash().hash
            if event.hash != recomputed:
                errors.append(f"hash mismatch at sequence {event.sequence}")
            previous_hash = event.hash
            terminal_hash = event.hash
        return ReplayReport(valid=not errors, checked_events=checked, errors=tuple(errors), terminal_hash=terminal_hash)
