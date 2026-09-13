import asyncio
from concurrent.futures import ThreadPoolExecutor
import pytest
from jep_openai_agents_middleware import JEPMiddleware, VerificationRuntime
from jep_openai_agents_middleware.delegation import DelegationTracker


def test_cancelled_tool_has_terminal_error(tmp_path):
    middleware = JEPMiddleware(tmp_path / "events.jsonl")
    async def cancel():
        raise asyncio.CancelledError()
    async def run():
        with pytest.raises(asyncio.CancelledError):
            await middleware.wrap_tool(cancel)()
    asyncio.run(run())
    events = middleware.archive.read_events()
    assert events[-1].payload["subject"] == "tool.error"
    assert events[-1].payload["status"] == "cancelled"
    assert middleware.verify_replay().valid


def test_multiple_archive_instances_serialize_append_and_reject_corruption(tmp_path):
    path = tmp_path / "events.jsonl"
    runtimes = [VerificationRuntime(path) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: runtimes[i % 8].judgment("call", {"i": i}), range(40)))
    assert runtimes[0].verify().valid
    assert runtimes[0].verify().checked_events == 40
    assert runtimes[0].verify([]).checked_events == 0
    path.write_text(path.read_text().replace('"call"', '"evil"', 1))
    before = path.read_bytes()
    with pytest.raises(ValueError):
        runtimes[0].judgment("call", {})
    assert path.read_bytes() == before


def test_tracker_isolated_between_tasks_and_resets_after_run():
    tracker = DelegationTracker()
    class Agent:
        def __init__(self, name): self.name = name
    async def run(name):
        agent = Agent(name)
        tracker.start_agent(agent)
        await asyncio.sleep(0)
        assert [item["name"] for item in tracker.lineage] == [name]
        tracker.end_agent(agent)
        assert tracker.snapshot() == {"lineage": [], "edges": []}
    async def both(): await asyncio.gather(run("a"), run("b"))
    asyncio.run(both())


def test_archive_rejects_sequence_coercion(tmp_path):
    import json
    runtime = VerificationRuntime(tmp_path / "events.jsonl")
    runtime.judgment("start", {})
    data = json.loads(runtime.archive.path.read_text())
    data["sequence"] = str(data["sequence"])
    runtime.archive.path.write_text(json.dumps(data) + "\n")
    with pytest.raises(ValueError): runtime.archive.read_events()
