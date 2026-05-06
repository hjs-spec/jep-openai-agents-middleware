"""Approval-required execution pattern with explicit JEP event capture."""

from jep_openai_agents_middleware import JEPMiddleware

middleware = JEPMiddleware("jep-approval.jsonl")


def wire_transfer(amount: int, destination: str) -> str:
    """A sensitive tool that should be wrapped and gated by application policy."""
    return f"queued transfer of {amount} to {destination}"


class AgentLike:
    name = "Finance Agent"


approval_id = "approval-123"
middleware.record_approval_required(AgentLike(), wire_transfer, approval_id, authority_scope="finance:transfer")
wrapped_transfer = middleware.wrap_tool(wire_transfer, agent=AgentLike(), authority_scope="finance:transfer")
print(wrapped_transfer(100, "vendor"))
print(middleware.verify_replay())
