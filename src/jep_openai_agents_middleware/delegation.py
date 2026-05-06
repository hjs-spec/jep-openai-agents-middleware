"""Agent lineage and delegation tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def agent_identity(agent: Any) -> dict[str, Any]:
    return {
        "name": getattr(agent, "name", agent.__class__.__name__ if agent is not None else "unknown"),
        "class": agent.__class__.__name__ if agent is not None else "None",
        "id": getattr(agent, "id", None) or hex(id(agent)) if agent is not None else None,
    }


@dataclass
class DelegationTracker:
    """Maintains agent lineage without changing SDK handoff semantics."""

    lineage: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)

    def start_agent(self, agent: Any) -> dict[str, Any]:
        identity = agent_identity(agent)
        if not self.lineage or self.lineage[-1] != identity:
            self.lineage.append(identity)
        return {"agent": identity, "lineage": list(self.lineage)}

    def record_delegation(self, source: Any, target: Any, kind: str = "handoff", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        source_identity = agent_identity(source)
        target_identity = agent_identity(target)
        edge = {
            "kind": kind,
            "from": source_identity,
            "to": target_identity,
            "authority_scope": (metadata or {}).get("authority_scope", "inherit"),
            "metadata": metadata or {},
        }
        self.edges.append(edge)
        if not self.lineage or self.lineage[-1] != target_identity:
            self.lineage.append(target_identity)
        return {"edge": edge, "lineage": list(self.lineage), "edges": list(self.edges)}

    def snapshot(self) -> dict[str, Any]:
        return {"lineage": list(self.lineage), "edges": list(self.edges)}
