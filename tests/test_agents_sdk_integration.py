"""Exercise real SDK scheduling without network calls or exported traces."""
import asyncio
import pytest

agents = pytest.importorskip("agents")
from agents import Agent, Runner, RunConfig
from agents.models.interface import Model
from agents.items import ModelResponse
from agents.usage import Usage
from openai.types.responses import ResponseOutputMessage, ResponseOutputText
from jep_openai_agents_middleware import JEPMiddleware


class LocalModel(Model):
    async def get_response(self, *args, **kwargs):
        return ModelResponse(output=[ResponseOutputMessage(id="local-message", role="assistant", status="completed",
            content=[ResponseOutputText(type="output_text", text="done", annotations=[])], type="message")],
            usage=Usage(), response_id="local-response")

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError
        yield


def test_real_runner_hook_tasks_retain_lineage(tmp_path):
    middleware = JEPMiddleware(tmp_path / "events.jsonl")
    agent = Agent(name="Local", model=LocalModel())
    async def run():
        result = await Runner.run(agent, "test", hooks=middleware.run_hooks, run_config=RunConfig(tracing_disabled=True))
        assert result.final_output == "done"
    asyncio.run(run())
    events = middleware.archive.read_events()
    terminal = [event for event in events if event.event_type == "termination"]
    assert len(terminal) == 1
    assert [item["name"] for item in terminal[0].payload["lineage"]] == ["Local"]
    assert not middleware.tracker._runs
    assert middleware.verify_replay().valid
