"""OpenAI Agents SDK handoff example with JEP accountability.

Run after installing the optional SDK dependency and setting OPENAI_API_KEY:
    pip install 'jep-openai-agents-middleware[openai-agents]'
    python examples/agent_handoff.py
"""

from agents import Agent, Runner, handoff

from jep_openai_agents_middleware import JEPMiddleware

middleware = JEPMiddleware("jep-handoff.jsonl")

billing_agent = Agent(name="Billing agent", instructions="Handle billing questions.")
refund_agent = Agent(name="Refund agent", instructions="Handle refund questions.")
triage_agent = Agent(
    name="Triage agent",
    instructions="Route the customer to the right specialist.",
    handoffs=[handoff(billing_agent), handoff(refund_agent)],
)

result = Runner.run_sync(triage_agent, "I was charged twice and need a refund.", hooks=middleware.hooks())
print(result.final_output)
print(middleware.verify_replay())
