"""Deterministic JEP event primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping
from uuid import uuid4


def _normalize(value: Any) -> Any:
    """Convert arbitrary Python values into stable JSON-compatible data."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _normalize(value[k]) for k in sorted(value, key=lambda item: str(item))}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, set):
        return [_normalize(item) for item in sorted(value, key=repr)]
    if hasattr(value, "model_dump"):
        return _normalize(value.model_dump())
    if hasattr(value, "dict"):
        return _normalize(value.dict())
    if hasattr(value, "__dict__"):
        return _normalize({k: v for k, v in vars(value).items() if not k.startswith("_")})
    return repr(value)


def canonical_json(value: Any) -> str:
    """Serialize values as canonical JSON for deterministic hashing."""
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deterministic_hash(value: Any) -> str:
    """Return a SHA-256 hash over canonical JSON."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JEPEvent:
    """Append-only portable accountability event.

    The hash is calculated over all event fields except ``hash``. ``prev_hash``
    links the event to the previous archive entry, producing a replay chain.
    """

    event_type: str
    run_id: str
    sequence: int
    prev_hash: str | None
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    hash: str = ""

    def material(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("hash", None)
        data["payload"] = _normalize(data["payload"])
        return data

    def with_hash(self) -> "JEPEvent":
        event_hash = deterministic_hash(self.material())
        return JEPEvent(
            event_type=self.event_type,
            run_id=self.run_id,
            sequence=self.sequence,
            prev_hash=self.prev_hash,
            payload=self.payload,
            event_id=self.event_id,
            created_at=self.created_at,
            hash=event_hash,
        )

    def to_json_line(self) -> str:
        return canonical_json(asdict(self)) + "\n"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "JEPEvent":
        required = {"event_type", "run_id", "sequence", "prev_hash", "payload", "event_id", "created_at", "hash"}
        if not isinstance(data, Mapping) or set(data) != required:
            raise ValueError("invalid archive event members")
        if type(data["sequence"]) is not int or not isinstance(data["payload"], Mapping):
            raise ValueError("invalid archive event types")
        for field in ("event_type", "run_id", "event_id", "created_at", "hash"):
            if not isinstance(data[field], str) or not data[field]:
                raise ValueError("invalid archive event string")
        if data["prev_hash"] is not None and not isinstance(data["prev_hash"], str):
            raise ValueError("invalid previous hash")
        return cls(
            event_type=data["event_type"],
            run_id=data["run_id"],
            sequence=data["sequence"],
            prev_hash=data.get("prev_hash"),
            payload=data.get("payload", {}),
            event_id=data["event_id"],
            created_at=data["created_at"],
            hash=data["hash"],
        )
