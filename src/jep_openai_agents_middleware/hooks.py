"""OpenAI Agents SDK lifecycle hooks that emit JEP events."""

from __future__ import annotations

from typing import Any

from .archive import VerificationRuntime
from .delegation import DelegationTracker, agent_identity
from .events import deterministic_hash

import importlib
import importlib.util

_agents_module = importlib.import_module("agents") if importlib.util.find_spec("agents") else None
if _agents_module is not None:
    _RunHooks = _agents_module.RunHooks
    _AgentHooks = _agents_module.AgentHooks
else:  # pragma: no cover - exercised only without SDK installed
    class _RunHooks:  # type: ignore[no-redef]
        pass

    class _AgentHooks:  # type: ignore[no-redef]
        pass


def _tool_payload(tool: Any) -> dict[str, Any]:
    return {"name": getattr(tool, "name", None) or getattr(tool, "__name__", None) or tool.__class__.__name__, "class": tool.__class__.__name__}


class AgentExecutionHook(_RunHooks):
    """Run-wide OpenAI Agents SDK hook that creates JEP events."""

    def __init__(self, runtime: VerificationRuntime, tracker: DelegationTracker | None = None, authority_scope: str = "agent:run"):
        self.runtime = runtime
        self.tracker = tracker or DelegationTracker()
        self.authority_scope = authority_scope

    async def on_agent_start(self, context: Any, agent: Any) -> None:
        snapshot = self.tracker.start_agent(agent, context)
        self.runtime.judgment("agent.start", {**snapshot, "authority_scope": self.authority_scope, "context_hash": deterministic_hash(context)})

    async def on_agent_end(self, context: Any, agent: Any, output: Any) -> None:
        self.runtime.termination({
            "agent": agent_identity(agent),
            "lineage": self.tracker.snapshot(context)["lineage"],
            "authority_scope": self.authority_scope,
            "output_hash": deterministic_hash(output),
            "context_hash": deterministic_hash(context),
        })

        self.tracker.end_agent(agent, context)

    async def on_handoff(self, context: Any, from_agent: Any, to_agent: Any) -> None:
        payload = self.tracker.record_delegation(from_agent, to_agent, kind="handoff", metadata={"context_hash": deterministic_hash(context)}, context=context)
        self.runtime.delegation(payload)

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        self.runtime.judgment("tool.start", {
            "agent": agent_identity(agent),
            "tool": _tool_payload(tool),
            "authority_scope": "tool:local",
            "context_hash": deterministic_hash(context),
            "lineage": self.tracker.snapshot(context)["lineage"],
        })

    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: str) -> None:
        self.runtime.judgment("tool.end", {
            "agent": agent_identity(agent),
            "tool": _tool_payload(tool),
            "authority_scope": "tool:local",
            "result_hash": deterministic_hash(result),
            "context_hash": deterministic_hash(context),
            "lineage": self.tracker.snapshot(context)["lineage"],
        })

    async def on_llm_start(self, context: Any, agent: Any, system_prompt: str | None, input_items: list[Any]) -> None:
        self.runtime.judgment("llm.start", {
            "agent": agent_identity(agent),
            "authority_scope": self.authority_scope,
            "system_prompt_hash": deterministic_hash(system_prompt),
            "input_hash": deterministic_hash(input_items),
        })

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
        self.runtime.judgment("llm.end", {
            "agent": agent_identity(agent),
            "authority_scope": self.authority_scope,
            "response_hash": deterministic_hash(response),
        })


class AgentScopedExecutionHook(_AgentHooks):
    """Agent-scoped hook variant for attaching to ``agent.hooks``."""

    def __init__(self, run_hook: AgentExecutionHook):
        self.run_hook = run_hook

    async def on_start(self, context: Any, agent: Any) -> None:
        await self.run_hook.on_agent_start(context, agent)

    async def on_end(self, context: Any, agent: Any, output: Any) -> None:
        await self.run_hook.on_agent_end(context, agent, output)

    async def on_handoff(self, context: Any, agent: Any, source: Any) -> None:
        await self.run_hook.on_handoff(context, source, agent)

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        await self.run_hook.on_tool_start(context, agent, tool)

    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: str) -> None:
        await self.run_hook.on_tool_end(context, agent, tool, result)

    async def on_llm_start(self, context: Any, agent: Any, system_prompt: str | None, input_items: list[Any]) -> None:
        await self.run_hook.on_llm_start(context, agent, system_prompt, input_items)

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
        await self.run_hook.on_llm_end(context, agent, response)
