"""
External HTTP agent adapter (issue #169).

Lets Yoke Agent evaluate agents that live behind an HTTP endpoint — your
production chatbot, a Langwatch-style agent, an OpenAI-compatible endpoint,
or any custom service that speaks JSON over HTTP.

The adapter speaks three response shapes, in order of preference:

1. **Yoke native** — `{"content": "...", "tool_calls": [...]}`.
   Most explicit. If the caller reports tool_calls, we trust them verbatim
   and feed them directly to the evaluator — no parsing, no ambiguity.

2. **OpenAI-compatible** — `{"choices": [{"message": {"content": "...",
   "tool_calls": [{"id": "...", "type": "function", "function": {"name":
   "...", "arguments": "<json string>"}}]}}]}`.
   Works out-of-the-box for most production LLM agents.

3. **Plain text fallback** — any 2xx response whose body contains a
   "content" field OR whose text body matches the `TOOL_CALL:` sandbox
   pattern. In this case we reuse `_parse_tool_calls` from the simulation
   engine so behaviour is identical to the built-in agent.

Request shape (what we POST to the external endpoint):

    {
        "session_id": "<combination_id>-<interaction_idx>",
        "turn": 1,
        "messages": [
            {"role": "system", "content": "..."},        # optional
            {"role": "user", "content": "Hi there"},
            {"role": "assistant", "content": "Hello!"},
            ...
        ],
        "scenario": {"name": "...", "type": "...", "objective": "..."},
        "persona": {"name": "...", "role": "...", "traits": [...]},
        "metadata": {"yoke": true, "variant_name": "..."}
    }

Agents that only understand the OpenAI chat-completions shape can ignore
the extra fields; only `messages` is standard.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import httpx

from app.models.agent import AgentConfig, Persona, Scenario

logger = logging.getLogger(__name__)


class ExternalAgentError(RuntimeError):
    """Raised when the external HTTP agent fails or returns an unusable response."""


def _messages_to_wire(messages: list[Any]) -> list[dict]:
    """Convert LangChain messages (or dicts) to the wire format."""
    out: list[dict] = []
    for m in messages:
        if isinstance(m, dict):
            role = m.get("role") or "user"
            content = m.get("content") or ""
        else:
            # LangChain BaseMessage
            cls_name = m.__class__.__name__
            role = {
                "SystemMessage": "system",
                "HumanMessage": "user",
                "AIMessage": "assistant",
            }.get(cls_name, "user")
            content = getattr(m, "content", "") or ""
        out.append({"role": role, "content": content})
    return out


def _normalize_tool_calls(raw: Any) -> list[dict]:
    """Normalize tool_calls into `[{tool_name, args, raw}]` shape.

    Accepts both:
      - Yoke native: `[{"tool_name": "x", "args": {...}}, ...]`
      - OpenAI:      `[{"id": "...", "type": "function",
                        "function": {"name": "x", "arguments": "<json>"}}]`
    """
    if not raw:
        return []
    if not isinstance(raw, list):
        return []

    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        # OpenAI-compatible
        if "function" in item and isinstance(item["function"], dict):
            fn = item["function"]
            name = fn.get("name", "unnamed_tool")
            arg_raw = fn.get("arguments")
            args: dict
            if isinstance(arg_raw, dict):
                args = arg_raw
            elif isinstance(arg_raw, str):
                try:
                    parsed = json.loads(arg_raw)
                    args = parsed if isinstance(parsed, dict) else {"value": parsed}
                except json.JSONDecodeError:
                    args = {"raw": arg_raw}
            else:
                args = {}
            out.append({"tool_name": name, "args": args, "raw": json.dumps(item)})
            continue

        # Yoke native
        name = item.get("tool_name") or item.get("name")
        if not name:
            continue
        args = item.get("args") or item.get("arguments") or {}
        if isinstance(args, str):
            try:
                parsed = json.loads(args)
                args = parsed if isinstance(parsed, dict) else {"value": parsed}
            except json.JSONDecodeError:
                args = {"raw": args}
        elif not isinstance(args, dict):
            args = {"value": args}
        out.append({"tool_name": name, "args": args, "raw": json.dumps(item)})
    return out


def _extract_content_and_tool_calls(
    data: Any,
) -> tuple[str, list[dict], str]:
    """Parse a parsed-JSON body and return `(content_text, tool_calls, format)`.

    `format` is one of `"native"`, `"openai"`, `"text"` — used by the
    test-connection endpoint to tell the user which shape was detected.
    """
    if isinstance(data, dict):
        # Yoke native — most explicit
        if "content" in data or "tool_calls" in data:
            content = data.get("content") or ""
            if not isinstance(content, str):
                content = json.dumps(content)
            tcs = _normalize_tool_calls(data.get("tool_calls"))
            return content, tcs, "native"

        # OpenAI chat completion
        if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
            first = data["choices"][0]
            if isinstance(first, dict):
                msg = first.get("message") or first.get("delta") or {}
                if isinstance(msg, dict):
                    content = msg.get("content") or ""
                    if not isinstance(content, str):
                        content = json.dumps(content)
                    tcs = _normalize_tool_calls(msg.get("tool_calls"))
                    return content, tcs, "openai"

        # Some backends just return `{"message": "..."}` or `{"response": "..."}`
        for key in ("message", "response", "output", "answer", "reply"):
            if key in data and isinstance(data[key], str):
                return data[key], [], "native"

    if isinstance(data, str):
        return data, [], "text"

    # Last resort: stringify whatever we got so the evaluator at least sees it
    return json.dumps(data), [], "text"


async def invoke_http_agent(
    config: AgentConfig,
    messages: list[Any],
    *,
    scenario: Optional[Scenario] = None,
    persona: Optional[Persona] = None,
    session_id: str = "",
    turn: int = 1,
    variant_name: Optional[str] = None,
) -> dict:
    """Call the external agent once and return `{content, tool_calls, format, latency_ms}`.

    Raises `ExternalAgentError` on transport failure, non-2xx response, or
    unparseable body. The caller (simulation engine) should catch this and
    record a failed turn so the experiment doesn't abort the whole run.
    """
    endpoint = (config.http_endpoint or "").strip()
    if not endpoint:
        raise ExternalAgentError("AgentConfig has no http_endpoint configured")

    timeout = float(getattr(config, "http_timeout_seconds", None) or 60)

    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    auth = (config.http_auth_header or "").strip()
    if auth:
        # Accept raw header value — e.g. "Bearer abc123" or "X-Api-Key: xyz".
        # If the user writes "Header-Name: value", split on the first colon.
        if ":" in auth and not auth.lower().startswith(("bearer ", "basic ")):
            name, _, value = auth.partition(":")
            headers[name.strip()] = value.strip()
        else:
            headers["Authorization"] = auth

    body: dict[str, Any] = {
        "session_id": session_id,
        "turn": turn,
        "messages": _messages_to_wire(messages),
    }
    if scenario is not None:
        body["scenario"] = {
            "name": getattr(scenario, "name", None),
            "type": getattr(scenario, "scenario_type", None),
            "objective": getattr(scenario, "objective", None),
        }
    if persona is not None:
        body["persona"] = {
            "name": getattr(persona, "name", None),
            "role": getattr(persona, "role", None),
            "traits": getattr(persona, "behavioral_traits", None) or [],
        }
    body["metadata"] = {
        "yoke": True,
        "variant_name": variant_name,
        "agent_config_id": getattr(config, "id", None),
    }

    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, headers=headers, json=body)
    except httpx.TimeoutException as e:
        raise ExternalAgentError(f"HTTP agent timed out after {timeout}s: {e}") from e
    except httpx.HTTPError as e:
        raise ExternalAgentError(f"HTTP agent transport error: {e}") from e

    latency_ms = int((time.time() - started) * 1000)

    if resp.status_code >= 400:
        preview = resp.text[:500] if resp.text else ""
        raise ExternalAgentError(
            f"HTTP agent returned {resp.status_code}: {preview}"
        )

    # Try JSON first, fall back to raw text
    try:
        data = resp.json()
    except (ValueError, json.JSONDecodeError):
        data = resp.text or ""

    content, tool_calls, fmt = _extract_content_and_tool_calls(data)

    # Fallback: if the external agent returned ONLY text (no structured
    # tool_calls field) but happens to use the same TOOL_CALL: convention as
    # the built-in sandbox, reuse the existing parser so behaviour matches.
    if not tool_calls and content:
        try:
            from app.services.agent_simulation_engine import _parse_tool_calls
            tool_calls = _parse_tool_calls(content)
        except Exception:
            pass

    return {
        "content": content or "",
        "tool_calls": tool_calls,
        "format": fmt,
        "latency_ms": latency_ms,
        "status_code": resp.status_code,
    }


async def test_http_agent_endpoint(
    http_endpoint: str,
    http_auth_header: Optional[str],
    http_timeout_seconds: int,
    sample_message: str = "Hello, this is a connection test from Yoke Agent.",
) -> dict:
    """Lightweight connectivity test used by the Define Agent form.

    Returns a result dict shaped like `TestHttpAgentResponse`. Never raises —
    wraps errors into the `ok=False` branch so the UI can render them.
    """
    # Build a stub AgentConfig-like object so we reuse invoke_http_agent.
    class _Stub:
        id = None
        http_endpoint = http_endpoint
        http_auth_header = http_auth_header
        http_timeout_seconds = http_timeout_seconds

    try:
        result = await invoke_http_agent(
            _Stub(),  # type: ignore[arg-type]
            [{"role": "user", "content": sample_message}],
            session_id="yoke-test-connection",
            turn=1,
            variant_name="test-connection",
        )
        preview = (result.get("content") or "")[:400]
        return {
            "ok": True,
            "status_code": result.get("status_code"),
            "response_preview": preview,
            "detected_format": result.get("format"),
            "tool_calls_detected": len(result.get("tool_calls") or []),
            "latency_ms": result.get("latency_ms"),
            "error": None,
        }
    except ExternalAgentError as e:
        return {
            "ok": False,
            "status_code": None,
            "response_preview": None,
            "detected_format": None,
            "tool_calls_detected": 0,
            "latency_ms": None,
            "error": str(e),
        }
    except Exception as e:  # pragma: no cover — safety net
        logger.exception("Unexpected error in test_http_agent_endpoint")
        return {
            "ok": False,
            "status_code": None,
            "response_preview": None,
            "detected_format": None,
            "tool_calls_detected": 0,
            "latency_ms": None,
            "error": f"{type(e).__name__}: {e}",
        }
