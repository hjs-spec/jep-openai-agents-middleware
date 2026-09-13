"""Tool wrappers that record JEP execution events."""

from __future__ import annotations

import functools
import asyncio
import inspect
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar

from .archive import VerificationRuntime
from .delegation import agent_identity
from .events import deterministic_hash

P = ParamSpec("P")
R = TypeVar("R")


def _tool_name(tool: Any) -> str:
    return getattr(tool, "name", None) or getattr(tool, "__name__", None) or tool.__class__.__name__


class ToolInvocationWrapper:
    """Wrap local tool invocations with judgment events.

    The wrapper supports normal functions and coroutine functions. It records
    start/end/error events while delegating the actual invocation unchanged.
    """

    def __init__(self, runtime: VerificationRuntime, authority_scope: str = "tool:local"):
        self.runtime = runtime
        self.authority_scope = authority_scope

    def start_payload(self, tool: Any, args: tuple[Any, ...], kwargs: dict[str, Any], agent: Any = None) -> dict[str, Any]:
        return {
            "tool": {"name": _tool_name(tool), "class": tool.__class__.__name__},
            "agent": agent_identity(agent) if agent is not None else None,
            "authority_scope": self.authority_scope,
            "arguments_hash": deterministic_hash({"args": args, "kwargs": kwargs}),
        }

    def end_payload(self, tool: Any, result: Any, agent: Any = None) -> dict[str, Any]:
        return {
            "tool": {"name": _tool_name(tool), "class": tool.__class__.__name__},
            "agent": agent_identity(agent) if agent is not None else None,
            "authority_scope": self.authority_scope,
            "result_hash": deterministic_hash(result),
            "result_type": type(result).__name__,
        }

    def wrap_callable(self, func: Callable[P, R], *, agent: Any = None, authority_scope: str | None = None) -> Callable[P, R] | Callable[P, Awaitable[R]]:
        scope = authority_scope or self.authority_scope
        child = ToolInvocationWrapper(self.runtime, authority_scope=scope)

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
                start = child.start_payload(func, args, kwargs, agent)
                child.runtime.judgment("tool.start", start)
                try:
                    result = await func(*args, **kwargs)
                except BaseException as exc:
                    child.runtime.judgment("tool.error", {**start, "error_type": type(exc).__name__, "status": "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"})
                    raise
                child.runtime.judgment("tool.end", child.end_payload(func, result, agent))
                return result

            return async_wrapped

        @functools.wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            start = child.start_payload(func, args, kwargs, agent)
            child.runtime.judgment("tool.start", start)
            try:
                result = func(*args, **kwargs)
            except BaseException as exc:
                child.runtime.judgment("tool.error", {**start, "error_type": type(exc).__name__, "status": "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"})
                raise
            child.runtime.judgment("tool.end", child.end_payload(func, result, agent))
            return result

        return wrapped
