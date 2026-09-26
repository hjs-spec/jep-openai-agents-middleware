# jep-openai-agents-middleware

> **Maintenance: retired experiment — 2026-09-26.** Active feature development
> has ended. Source history, releases, examples and existing archive readers are
> retained for reproduction. Package names and historical formats are unchanged.

The unsigned Agents SDK RunHooks archive and instrumentation remain available here. The maintained Agent SDK provides signed callable recording, not an equivalent RunHooks implementation or an old-archive decoder.

For new signed Core integrations, use the [maintained recording and report path](https://github.com/hjs-spec/jep-agent-sdk/blob/main/docs/INTEGRATIONS.md).
See the [repository directory](https://github.com/hjs-spec/.github/blob/main/PROJECTS.md#retired-experiments) for maintenance status. No automatic archive migration is provided.

Execution observation and replay archives for the OpenAI Agents SDK.

This package observes SDK lifecycle hooks and wraps local tool callables without forking the SDK or changing its core semantics. It records execution metadata, declared delegation, and authority scope in a local hash-linked JSONL archive.

## Event format and verification scope

This package emits **local execution-observation envelopes**, not signed [JEP Core 0.7](https://github.com/hjs-spec/jep-core) wire events. Its `event_type`, `run_id`, `sequence`, `prev_hash`, and `payload` fields belong to the middleware archive format. It does not produce detached-JWS signatures or perform Core signature and key-trust validation. Core interoperability requires a separately specified mapping and signing implementation.

`middleware.verify_replay().valid` reports sequence, previous-hash, and payload-hash consistency within the supplied archive. It does not establish actor identity, permission to act, the correctness of a model response, or the truth of an external claim. Declared authority scope and approval-related records do not themselves enforce authorization.

## What is recorded

The middleware maps observed callbacks and explicit instrumentation to local event labels:

- **Judgment events** for agent starts, LLM calls, tool starts/ends/errors, approval-required execution, and other local execution decisions.
- **Delegation events** for handoffs and explicit sub-agent delegation.
- **Termination events** when an agent produces final output.

These labels describe the middleware's instrumentation mapping. For example, recording an agent start as a judgment event does not establish that a substantive external decision occurred.

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

Events are stored as JSON Lines. The writer assigns increasing sequence numbers and links each new event to the previous hash. Hashes use SHA-256 over this package's deterministic JSON serialization; this is not a claim of JEP-Core canonicalization conformance.

Replay reports edits, gaps, or reordering when they break the checked hashes, sequence, or links. A successful result concerns the supplied records, not proof that every execution event was captured.

The writer appends records, but an unkeyed hash chain alone cannot rule out a complete rewrite or removal of a valid suffix. Detecting those changes requires an independently trusted checkpoint or other external evidence of the expected history.

## Runtime and verification notes

See [HARDENING.md](HARDENING.md) for supported behavior, regression checks, and compatibility boundaries.
