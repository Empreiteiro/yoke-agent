"""
External HTTP agent adapter (issue #169).

Lets Yoke Agent evaluate agents that live behind an HTTP endpoint — your
production chatbot, a Langwatch-style agent, an OpenAI-compatible endpoint,
or any custom service that speaks JSON over HTTP.

# Request shape

Two modes, selected by the presence of `http_body_template` on the config:

1. **Template mode** (recommended). The user writes a JSON template with
   `{{var}}` placeholders. We render it at runtime with the available
   variables and POST it verbatim. Works with ANY endpoint shape —
   OpenAI-compatible, custom `{"query": "..."}`, whatever.

   Variables available in the template:
     {{user_message}}       — current user-simulator message
     {{messages}}           — full [{role, content}, ...] array (JSON value)
     {{messages_text}}      — concatenated history as plain text
     {{session_id}}         — stable conversation id ("<combo>-<interaction>")
     {{turn}}               — 1, 2, 3...
     {{scenario_name}}, {{scenario_type}}, {{scenario_objective}}
     {{persona_name}}, {{persona_role}}, {{persona_traits}}
     {{variant_name}}

   Substitution rules:
     - `"{{var}}"` (with explicit surrounding quotes) → string
       interpolation. The quotes stay, and the string value is JSON-escaped
       inside them. Use for text values.
     - `{{var}}` (bare, no quotes) → JSON value injection. The variable is
       serialized as a JSON value (`"..."` for strings, `[...]` for arrays,
       etc.). Use for arrays and objects like `{{messages}}`.

2. **Native mode** (fallback when `http_body_template` is empty). We POST
   the original Yoke shape — `{session_id, turn, messages, scenario,
   persona, metadata}` — so anything that worked before keeps working.

# Response shape

Three shapes, checked in order:

1. **Explicit paths** (when `http_response_path` / `http_tool_calls_path`
   are set on the config). We extract content and tool_calls from those
   dotted paths (e.g. `choices[0].message.content`). Works with any
   response shape.

2. **Auto-detection** — Yoke native (`{content, tool_calls}`), OpenAI
   chat-completion (`choices[0].message.tool_calls`), then common aliases
   (`message`, `response`, `output`, `answer`, `reply`).

3. **Plain text fallback** — any 2xx body whose content mentions
   `TOOL_CALL: name({...})` lines. Reuses the sandbox parser so behaviour
   matches the built-in agent.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

import httpx

from app.models.agent import AgentConfig, Persona, Scenario

logger = logging.getLogger(__name__)


class ExternalAgentError(RuntimeError):
    """Raised when the external HTTP agent fails or returns an unusable response."""


# ── Variable context builders ────────────────────────────────────────


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


def _build_template_context(
    messages: list[dict],
    *,
    scenario: Optional[Scenario] = None,
    persona: Optional[Persona] = None,
    session_id: str = "",
    turn: int = 1,
    variant_name: Optional[str] = None,
) -> dict:
    """Build the `{{var}}` context dict used by `_render_body_template`."""
    # Last user message = what the simulator just said this turn
    user_message = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_message = m.get("content") or ""
            break

    messages_text = "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
    )

    return {
        "user_message": user_message,
        "messages": messages,
        "messages_text": messages_text,
        "session_id": session_id,
        "turn": turn,
        "scenario_name": getattr(scenario, "name", "") or "",
        "scenario_type": getattr(scenario, "scenario_type", "") or "",
        "scenario_objective": getattr(scenario, "objective", "") or "",
        "persona_name": getattr(persona, "name", "") or "",
        "persona_role": getattr(persona, "role", "") or "",
        "persona_traits": getattr(persona, "behavioral_traits", None) or [],
        "variant_name": variant_name or "",
    }


# ── Template rendering ───────────────────────────────────────────────


# `"{{var}}"` — string interpolation (quotes in template, value gets
# JSON-escaped inside them). Matched BEFORE bare {{var}} so the quoted
# form wins when both patterns could apply.
_STRING_VAR_RE = re.compile(r'"{{\s*(\w+)\s*}}"')

# Bare `{{var}}` — JSON-value injection (no surrounding quotes).
_BARE_VAR_RE = re.compile(r"{{\s*(\w+)\s*}}")


def _render_body_template(template: str, context: dict) -> str:
    """Render a JSON template by substituting `{{var}}` placeholders.

    Returns the rendered string (still needs JSON-parsing by caller if
    they want a dict). Raises `ExternalAgentError` if the result is not
    valid JSON.
    """
    if not template or not template.strip():
        raise ExternalAgentError("http_body_template is empty")

    def _sub_string(m: re.Match) -> str:
        key = m.group(1)
        val = context.get(key)
        if val is None:
            val = ""
        if not isinstance(val, (str, int, float, bool)):
            # Non-string → JSON-encode to a string representation
            try:
                val = json.dumps(val, ensure_ascii=False)
            except (TypeError, ValueError):
                val = str(val)
        return json.dumps(str(val), ensure_ascii=False)

    def _sub_bare(m: re.Match) -> str:
        key = m.group(1)
        val = context.get(key)
        try:
            return json.dumps(val, ensure_ascii=False)
        except (TypeError, ValueError):
            return json.dumps(str(val), ensure_ascii=False)

    rendered = _STRING_VAR_RE.sub(_sub_string, template)
    rendered = _BARE_VAR_RE.sub(_sub_bare, rendered)

    # Validate: caller will want to json.loads this.
    try:
        json.loads(rendered)
    except json.JSONDecodeError as e:
        raise ExternalAgentError(
            f"Rendered body template is not valid JSON: {e.msg} at line {e.lineno} col {e.colno}"
        ) from e

    return rendered


# ── Response path extraction ─────────────────────────────────────────


_PATH_PART_RE = re.compile(r"[^.\[\]]+|\[\d+\]")


def _extract_by_path(data: Any, path: str) -> Any:
    """Extract a nested value using a dotted/indexed path.

    Supports `foo.bar`, `choices[0].message.content`, `data["reply"]`
    (brackets with integer indices only). Returns `None` if any segment
    is missing, rather than raising.
    """
    if not path:
        return None
    path = path.strip()
    parts = _PATH_PART_RE.findall(path)
    current: Any = data
    for part in parts:
        if current is None:
            return None
        if part.startswith("["):
            try:
                idx = int(part[1:-1])
            except ValueError:
                return None
            if isinstance(current, list) and 0 <= idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            part_clean = part.strip()
            if isinstance(current, dict):
                current = current.get(part_clean)
            else:
                return None
    return current


# ── Tool-call normalization ──────────────────────────────────────────


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
            args: Any
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
    *,
    response_path: Optional[str] = None,
    tool_calls_path: Optional[str] = None,
) -> tuple[str, list[dict], str]:
    """Parse a response body and return `(content_text, tool_calls, format)`.

    When `response_path` / `tool_calls_path` are provided, use them
    verbatim (format="template"). Otherwise fall back to auto-detection
    of Yoke native / OpenAI / common aliases / raw text.
    """
    # 1. Explicit paths win
    if response_path or tool_calls_path:
        content: Any = None
        if response_path:
            content = _extract_by_path(data, response_path)
        if content is None and isinstance(data, dict):
            # If response_path missed but data has a plain content field,
            # use it as a courtesy so a typo doesn't kill the whole run.
            content = data.get("content") or data.get("message") or ""
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False) if content is not None else ""

        tcs_raw: Any = None
        if tool_calls_path:
            tcs_raw = _extract_by_path(data, tool_calls_path)
        tcs = _normalize_tool_calls(tcs_raw) if tcs_raw is not None else []
        return content, tcs, "template"

    # 2. Auto-detect
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

        # Common aliases
        for key in ("message", "response", "output", "answer", "reply"):
            if key in data and isinstance(data[key], str):
                return data[key], [], "native"

    if isinstance(data, str):
        return data, [], "text"

    return json.dumps(data), [], "text"


# ── Default (native) body ────────────────────────────────────────────


def _build_native_body(
    messages: list[dict],
    *,
    scenario: Optional[Scenario],
    persona: Optional[Persona],
    session_id: str,
    turn: int,
    variant_name: Optional[str],
    agent_config_id: Optional[int],
) -> dict:
    """Build the Yoke native request body (used when there's no template)."""
    body: dict[str, Any] = {
        "session_id": session_id,
        "turn": turn,
        "messages": messages,
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
        "agent_config_id": agent_config_id,
    }
    return body


# ── Headers ──────────────────────────────────────────────────────────


def _build_headers(auth_header: Optional[str]) -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    auth = (auth_header or "").strip()
    if auth:
        # Accept raw header value — e.g. "Bearer abc123" or "X-Api-Key: xyz".
        # If the user writes "Header-Name: value", split on the first colon.
        if ":" in auth and not auth.lower().startswith(("bearer ", "basic ")):
            name, _, value = auth.partition(":")
            headers[name.strip()] = value.strip()
        else:
            headers["Authorization"] = auth
    return headers


# ── Main invoke ──────────────────────────────────────────────────────


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
    """Call the external agent once and return a result dict.

    Returned fields:
        content      — agent's text response
        tool_calls   — list of {tool_name, args, raw} dicts
        format       — "template" | "native" | "openai" | "text"
        latency_ms   — wall time for the POST
        status_code  — HTTP status code
        rendered_body — the JSON body that was actually sent

    Raises `ExternalAgentError` on transport failure, non-2xx response,
    template rendering error, or unparseable body.
    """
    endpoint = (config.http_endpoint or "").strip()
    if not endpoint:
        raise ExternalAgentError("AgentConfig has no http_endpoint configured")

    timeout = float(getattr(config, "http_timeout_seconds", None) or 60)

    wire_messages = _messages_to_wire(messages)

    # Choose request body: template if present, native otherwise.
    template = (getattr(config, "http_body_template", None) or "").strip()
    if template:
        ctx = _build_template_context(
            wire_messages,
            scenario=scenario,
            persona=persona,
            session_id=session_id,
            turn=turn,
            variant_name=variant_name,
        )
        rendered = _render_body_template(template, ctx)
        body_json = json.loads(rendered)
        body_str = rendered
    else:
        body_json = _build_native_body(
            wire_messages,
            scenario=scenario,
            persona=persona,
            session_id=session_id,
            turn=turn,
            variant_name=variant_name,
            agent_config_id=getattr(config, "id", None),
        )
        body_str = json.dumps(body_json, ensure_ascii=False)

    headers = _build_headers(config.http_auth_header)

    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, headers=headers, json=body_json)
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

    content, tool_calls, fmt = _extract_content_and_tool_calls(
        data,
        response_path=getattr(config, "http_response_path", None),
        tool_calls_path=getattr(config, "http_tool_calls_path", None),
    )

    # Fallback: if nobody reported tool_calls explicitly but the text
    # uses the same TOOL_CALL: convention as the built-in sandbox, reuse
    # the existing parser so behaviour matches.
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
        "rendered_body": body_str,
    }


# ── Connectivity test (Define Agent form's "Test connection" button) ─


async def test_http_agent_endpoint(
    http_endpoint: str,
    http_auth_header: Optional[str],
    http_timeout_seconds: int,
    sample_message: str = "Hello, this is a connection test from Yoke Agent.",
    http_body_template: Optional[str] = None,
    http_response_path: Optional[str] = None,
    http_tool_calls_path: Optional[str] = None,
) -> dict:
    """Fire one test call against an HTTP agent endpoint.

    Shaped to match `TestHttpAgentResponse`. Never raises — wraps errors
    into the `ok=False` branch so the UI can render them.
    """
    class _Stub:
        id = None
        http_endpoint = http_endpoint
        http_auth_header = http_auth_header
        http_timeout_seconds = http_timeout_seconds
        http_body_template = http_body_template
        http_response_path = http_response_path
        http_tool_calls_path = http_tool_calls_path

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
            "rendered_body": result.get("rendered_body"),
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
            "rendered_body": None,
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
            "rendered_body": None,
        }
