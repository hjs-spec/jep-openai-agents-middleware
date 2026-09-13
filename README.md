# jep-openai-agents-middleware

JEP middleware for the OpenAI Agents SDK: portable and replayable AI judgment verification.

This package adds **portable accountability semantics** to OpenAI agent execution without forking the OpenAI Agents SDK and without changing SDK core semantics. It observes lifecycle hooks and wraps local tool callables to write deterministic, append-only JEP events.

## What is recorded

The middleware automatically generates:

- **Judgment events** for agent starts, LLM calls, tool starts/ends/errors, approval-required execution, and other local execution decisions.
- **Delegation events** for handoffs and explicit sub-agent delegation.
- **Termination events** when an agent produces final output.

Each event can include:

- Agent lineage.
- Tool execution metadata.
- Authority scope.
- Execution replay chain metadata.
- Deterministic payload hashes instead of raw sensitive arguments/results.

## Core APIs

- `JEPMiddleware` — high-level facade for archive, hook, agent instrumentation, explicit delegation, and replay verification.
- `AgentExecutionHook` — run-wide OpenAI Agents SDK lifecycle hook compatible with `Runner.run(..., hooks=...)`.
- `ToolInvocationWrapper` — sync/async callable wrapper for local tool execution events.
- `DelegationTracker` — tracks lineage and handoff/sub-agent edges.
- `VerificationRuntime` — appends events and verifies deterministic replay hash chains.

## Basic usage with OpenAI Agents SDK

```python
from agents import Agent, Runner, handoff
from jep_openai_agents_middleware import JEPMiddleware

middleware = JEPMiddleware("jep-archive.jsonl")

billing_agent = Agent(name="Billing agent")
refund_agent = Agent(name="Refund agent")
triage_agent = Agent(
    name="Triage agent",
    handoffs=[handoff(billing_agent), handoff(refund_agent)],
)

result = await Runner.run(
    triage_agent,
    "I was charged twice and need a refund.",
    hooks=middleware.hooks(),
)

assert middleware.verify_replay().valid
```

## Wrapping local tools

```python
from jep_openai_agents_middleware import JEPMiddleware

middleware = JEPMiddleware("jep-tools.jsonl")

def lookup_order(order_id: str) -> str:
    return "shipped"

lookup_order = middleware.wrap_tool(lookup_order, authority_scope="orders:read")
lookup_order("order_123")
```

## Examples

- `examples/agent_handoff.py` — OpenAI Agents SDK handoff accountability.
- `examples/multi_agent_collaboration.py` — explicit multi-agent delegation tracking.
- `examples/approval_required_execution.py` — approval-required tool execution recording.

## Verification model

Events are stored as JSON Lines. The archive is append-only: new events receive a monotonically increasing sequence number and the previous event hash. Hashes are SHA-256 over canonical JSON, so replay verification can detect tampering, missing events, or reordered events.

## Runtime and verification notes

See [HARDENING.md](HARDENING.md) for supported behavior, regression checks, and compatibility boundaries.
