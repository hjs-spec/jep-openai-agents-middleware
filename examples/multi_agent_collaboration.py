"""Record sub-agent collaboration that is implemented outside SDK handoffs."""

from dataclasses import dataclass

from jep_openai_agents_middleware import JEPMiddleware


@dataclass
class AgentLike:
    name: str


middleware = JEPMiddleware("jep-collaboration.jsonl")
planner = AgentLike("Planner")
researcher = AgentLike("Researcher")
writer = AgentLike("Writer")

middleware.record_sub_agent_delegation(planner, researcher, authority_scope="research-only")
middleware.record_sub_agent_delegation(planner, writer, authority_scope="draft-only")
middleware.runtime.termination({"agent": writer.name, "output_hash": "external-run-output"})

print(middleware.verify_replay())
