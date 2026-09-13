"""Agent lineage scoped to an SDK run, including hooks dispatched in child tasks."""

from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
from threading import RLock
from typing import Any


def agent_identity(agent: Any) -> dict[str, Any]:
    return {
        "name": getattr(
            agent, "name", agent.__class__.__name__ if agent is not None else "unknown"
        ),
        "class": agent.__class__.__name__ if agent is not None else "None",
        "id": (
            (getattr(agent, "id", None) or hex(id(agent)))
            if agent is not None
            else None
        ),
    }


class DelegationTracker:
    """Use SDK usage identity across hook tasks; explicit calls use task-local state."""

    def __init__(self):
        self._local = ContextVar("jep_agent_lineage", default=None)
        self._runs: dict[int, tuple[Any, dict]] = {}
        self._lock = RLock()

    def _read(self, context=None):
        owner = getattr(context, "usage", None)
        if owner is None:
            return deepcopy(self._local.get() or {"lineage": [], "edges": []})
        entry = self._runs.get(id(owner))
        return (
            deepcopy(entry[1])
            if entry is not None and entry[0] is owner
            else {"lineage": [], "edges": []}
        )

    def _write(self, state, context=None):
        owner = getattr(context, "usage", None)
        if owner is None:
            self._local.set(state)
        else:
            self._runs[id(owner)] = (owner, state)

    @property
    def lineage(self):
        return self.snapshot()["lineage"]

    @property
    def edges(self):
        return self.snapshot()["edges"]

    def start_agent(self, agent: Any, context=None) -> dict[str, Any]:
        identity = agent_identity(agent)
        with self._lock:
            state = self._read(context)
            if not state["lineage"] or state["lineage"][-1] != identity:
                state["lineage"].append(identity)
            self._write(state, context)
            return {"agent": identity, "lineage": deepcopy(state["lineage"])}

    def end_agent(self, agent: Any, context=None) -> None:
        with self._lock:
            owner = getattr(context, "usage", None)
            if owner is None:
                self._local.set(None)
            else:
                self._runs.pop(id(owner), None)

    def record_delegation(
        self,
        source: Any,
        target: Any,
        kind: str = "handoff",
        metadata: dict[str, Any] | None = None,
        context=None,
    ) -> dict[str, Any]:
        source_identity, target_identity = agent_identity(source), agent_identity(
            target
        )
        edge = {
            "kind": kind,
            "from": source_identity,
            "to": target_identity,
            "authority_scope": (metadata or {}).get("authority_scope", "inherit"),
            "metadata": deepcopy(metadata or {}),
        }
        with self._lock:
            state = self._read(context)
            state["edges"].append(edge)
            if not state["lineage"]:
                state["lineage"].append(source_identity)
            if state["lineage"][-1] != target_identity:
                state["lineage"].append(target_identity)
            self._write(state, context)
            return {"edge": deepcopy(edge), **deepcopy(state)}

    def snapshot(self, context=None) -> dict[str, Any]:
        with self._lock:
            return self._read(context)
