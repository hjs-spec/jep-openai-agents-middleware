"""Public middleware facade for OpenAI Agents SDK integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, ParamSpec, TypeVar

from .archive import AppendOnlyArchive, VerificationRuntime
from .delegation import DelegationTracker
from .hooks import AgentExecutionHook, AgentScopedExecutionHook
from .tools import ToolInvocationWrapper

P = ParamSpec("P")
R = TypeVar("R")


class JEPMiddleware:
    """Facade for adding JEP accountability to an Agents SDK run.

    Use ``middleware.run_hooks`` with ``Runner.run(..., hooks=...)`` for
    run-wide observation. Use ``instrument_agent`` when an agent should carry
    agent-scoped hooks. Use ``wrap_tool`` for explicit callable wrapping in code
    paths that do not trigger SDK tool lifecycle hooks.
    """

    def __init__(self, archive_path: str | Path = "jep-archive.jsonl", run_id: str | None = None, authority_scope: str = "agent:run"):
        self.archive = AppendOnlyArchive(archive_path)
        self.runtime = VerificationRuntime(self.archive, run_id=run_id)
        self.tracker = DelegationTracker()
        self.run_hooks = AgentExecutionHook(self.runtime, tracker=self.tracker, authority_scope=authority_scope)
        self.tool_wrapper = ToolInvocationWrapper(self.runtime)

    def hooks(self) -> AgentExecutionHook:
        """Return the run-wide hook object for ``Runner.run(..., hooks=...)``."""
        return self.run_hooks

    def agent_hooks(self) -> AgentScopedExecutionHook:
        """Return an agent-scoped hook object for assigning to ``agent.hooks``."""
        return AgentScopedExecutionHook(self.run_hooks)

    def instrument_agent(self, agent: Any) -> Any:
        """Attach JEP agent-scoped hooks and return the same agent instance."""
        setattr(agent, "hooks", self.agent_hooks())
        return agent

    def wrap_tool(self, func: Callable[P, R], *, agent: Any = None, authority_scope: str | None = None) -> Callable[P, R]:
        """Wrap a tool callable with JEP start/end/error judgment events."""
        return self.tool_wrapper.wrap_callable(func, agent=agent, authority_scope=authority_scope)  # type: ignore[return-value]

    def record_sub_agent_delegation(self, from_agent: Any, to_agent: Any, *, authority_scope: str = "delegated", metadata: dict[str, Any] | None = None) -> None:
        """Record an explicit sub-agent delegation outside SDK handoff hooks."""
        details = {"authority_scope": authority_scope, **(metadata or {})}
        payload = self.tracker.record_delegation(from_agent, to_agent, kind="sub_agent", metadata=details)
        self.runtime.delegation(payload)

    def record_approval_required(self, agent: Any, tool: Any, approval_id: str, authority_scope: str) -> None:
        """Record that an execution path is paused pending approval."""
        self.runtime.judgment("approval.required", {
            "agent": getattr(agent, "name", repr(agent)),
            "tool": getattr(tool, "name", None) or getattr(tool, "__name__", repr(tool)),
            "approval_id": approval_id,
            "authority_scope": authority_scope,
        })

    def verify_replay(self):
        """Verify the archive hash chain."""
        return self.runtime.verify()
