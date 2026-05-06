from __future__ import annotations

import asyncio
import json

from jep_openai_agents_middleware import JEPMiddleware, VerificationRuntime


class AgentLike:
    def __init__(self, name: str):
        self.name = name


class ToolLike:
    name = "lookup"


def test_tool_wrapper_records_start_end_and_verifies(tmp_path):
    middleware = JEPMiddleware(tmp_path / "archive.jsonl", run_id="run-test")

    def add(a: int, b: int) -> int:
        return a + b

    wrapped = middleware.wrap_tool(add, agent=AgentLike("Calculator"), authority_scope="math:add")
    assert wrapped(2, 3) == 5

    events = middleware.archive.read_events()
    assert [event.payload["subject"] for event in events] == ["tool.start", "tool.end"]
    assert events[0].payload["authority_scope"] == "math:add"
    assert middleware.verify_replay().valid


def test_async_hook_records_handoff_tool_and_termination(tmp_path):
    middleware = JEPMiddleware(tmp_path / "archive.jsonl", run_id="run-hooks")
    source = AgentLike("Triage")
    target = AgentLike("Refund")
    tool = ToolLike()

    async def run_hooks():
        await middleware.run_hooks.on_agent_start({"request": 1}, source)
        await middleware.run_hooks.on_handoff({"reason": "refund"}, source, target)
        await middleware.run_hooks.on_tool_start({}, target, tool)
        await middleware.run_hooks.on_tool_end({}, target, tool, "ok")
        await middleware.run_hooks.on_agent_end({}, target, "done")

    asyncio.run(run_hooks())

    events = middleware.archive.read_events()
    assert [event.event_type for event in events] == ["judgment", "delegation", "judgment", "judgment", "termination"]
    assert events[1].payload["edge"]["kind"] == "handoff"
    assert events[-1].payload["lineage"][-1]["name"] == "Refund"
    assert middleware.verify_replay().valid


def test_replay_verification_detects_tampering(tmp_path):
    runtime = VerificationRuntime(tmp_path / "archive.jsonl", run_id="tamper")
    runtime.judgment("agent.start", {"agent": "A"})
    runtime.termination({"agent": "A"})

    lines = (tmp_path / "archive.jsonl").read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["payload"]["agent"] = "B"
    lines[0] = json.dumps(tampered)
    (tmp_path / "archive.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = runtime.verify()
    assert not report.valid
    assert any("hash mismatch" in error for error in report.errors)
