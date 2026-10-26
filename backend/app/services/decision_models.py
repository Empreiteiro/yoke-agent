"""Client for decision models that speak TypeSafe's System One API.

Decision models (TypeSafe's Jev, and open "Jev-style" models served behind
a compatible endpoint) don't generate text. The caller sends a piece of
*state* plus one or more typed *questions*; the model answers each question
with a calibrated choice and a probability distribution over the options.

Request shape (``POST {base_url}/v1/systemone``)::

    {
      "model": "jev-latest",
      "state": "I was charged twice this month…",
      "questions": {
        "decision": {
          "type": "choice",
          "instructions": "Which team should handle this ticket?",
          "criteria": {"billing": "Payments, invoices…", "technical": "Bugs…"}
        }
      }
    }

Response shape::

    {
      "model": "jev-…",
      "answers": {"decision": {"choice": "billing",
                               "probabilities": {"billing": 0.97, …},
                               "confidence": 0.97}},
      "usage": {"input_tokens": 84, "output_tokens": 0}
    }

Gateways and self-hosted servers differ slightly in naming, so the parser
below accepts the common variants (``answers``/``decisions``,
``choice``/``answer``/``value``, ``probabilities``/``scores``).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.models.provider import Provider

logger = logging.getLogger(__name__)

TYPESAFE_DEFAULT_BASE_URL = "https://api.typesafe.ai"
SYSTEMONE_PATH = "/v1/systemone"
QUESTION_KEY = "decision"
DECISION_PROVIDER_TYPES = {"typesafe", "systemone"}

# Retry transient upstream failures (rate limits, overloaded gateways).
_RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 4


class DecisionModelError(RuntimeError):
    """Raised when the decision endpoint returns an unusable response."""


@dataclass
class DecisionAnswer:
    choice: Optional[str]
    confidence: Optional[float] = None
    probabilities: dict[str, float] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_estimated: bool = False
    # Latency of the attempt that succeeded — backoff sleeps and failed
    # attempts are excluded so retries don't inflate the percentiles.
    latency_ms: float = 0.0
    attempts: int = 1
    raw: Any = None


def resolve_endpoint(provider: Provider) -> str:
    """Return the full System One URL for ``provider``.

    ``base_url`` may be the API root (``https://api.typesafe.ai``), a gateway
    prefix (``http://litellm:4000/typesafe``) or the full endpoint already
    ending in ``/systemone``. ``extra_config.path`` overrides the path.
    """
    base = (provider.base_url or "").strip()
    if not base:
        if provider.provider_type == "typesafe":
            base = TYPESAFE_DEFAULT_BASE_URL
        else:
            raise DecisionModelError(
                f"Provider '{provider.name}' needs a Base URL for its System One endpoint."
            )
    base = base.rstrip("/")
    if base.endswith("/systemone"):
        return base
    path = (provider.extra_config or {}).get("path") or SYSTEMONE_PATH
    return f"{base}/{path.lstrip('/')}"


def build_request(model: str, state: str, instructions: str, labels: list[dict]) -> dict:
    criteria = {
        label["name"]: (label.get("description") or label["name"]).strip()
        for label in labels
    }
    return {
        "model": model,
        "state": state,
        "questions": {
            QUESTION_KEY: {
                "type": "choice",
                "instructions": instructions,
                "criteria": criteria,
            }
        },
    }


def estimate_request_tokens(state: str, instructions: str, labels: list[dict]) -> int:
    """Rough char/4 estimate of billable input tokens for one request."""
    chars = len(state) + len(instructions)
    chars += sum(len(l["name"]) + len(l.get("description") or "") for l in labels)
    return max(1, chars // 4)


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_response(data: Any) -> DecisionAnswer:
    """Extract the choice, confidence and usage from a System One response."""
    if not isinstance(data, dict):
        raise DecisionModelError(f"Unexpected response type: {type(data).__name__}")

    answers = None
    for key in ("answers", "decisions", "results", "outputs"):
        if isinstance(data.get(key), (dict, list)):
            answers = data[key]
            break
    if answers is None:
        raise DecisionModelError(f"Response has no answers: {str(data)[:300]}")

    if isinstance(answers, dict):
        answer = answers.get(QUESTION_KEY)
        if answer is None and answers:
            answer = next(iter(answers.values()))
    else:
        answer = answers[0] if answers else None
    if answer is None:
        raise DecisionModelError("Response contains an empty answer set")

    choice: Optional[str] = None
    probabilities: dict[str, float] = {}
    confidence: Optional[float] = None
    if isinstance(answer, dict):
        for key in ("choice", "answer", "value", "label", "decision"):
            if isinstance(answer.get(key), str):
                choice = answer[key]
                break
        raw_probs = answer.get("probabilities") or answer.get("scores") or answer.get("distribution")
        if isinstance(raw_probs, dict):
            probabilities = {
                str(k): p for k, v in raw_probs.items() if (p := _to_float(v)) is not None
            }
        confidence = _to_float(answer.get("confidence", answer.get("probability")))
    elif isinstance(answer, str):
        choice = answer

    if choice is None and probabilities:
        choice = max(probabilities, key=probabilities.get)
    if confidence is None and probabilities and choice in probabilities:
        confidence = probabilities[choice]

    usage = data.get("usage") or {}
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)

    return DecisionAnswer(
        choice=choice,
        confidence=confidence,
        probabilities=probabilities,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        raw=data,
    )


class SystemOneClient:
    """Async client for one decision model on one provider."""

    def __init__(self, provider: Provider, model: str, timeout: float = 60.0):
        self.provider = provider
        self.model = model
        self.url = resolve_endpoint(provider)
        self.timeout = timeout
        headers = {"Content-Type": "application/json"}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        extra_headers = (provider.extra_config or {}).get("headers") or {}
        if isinstance(extra_headers, dict):
            headers.update({str(k): str(v) for k, v in extra_headers.items()})
        self.headers = headers

    def new_http_client(self, concurrency: int = 8) -> httpx.AsyncClient:
        limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
        return httpx.AsyncClient(timeout=self.timeout, limits=limits, headers=self.headers)

    async def decide(
        self,
        http: httpx.AsyncClient,
        state: str,
        instructions: str,
        labels: list[dict],
    ) -> DecisionAnswer:
        body = build_request(self.model, state, instructions, labels)
        last_error: Optional[Exception] = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            retry_after = 0.0
            started = time.perf_counter()
            try:
                resp = await http.post(self.url, json=body)
            except httpx.TransportError as e:
                last_error = e
            else:
                if resp.status_code in _RETRY_STATUS and attempt < _MAX_ATTEMPTS:
                    last_error = DecisionModelError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                    retry_after = min(_to_float(resp.headers.get("retry-after")) or 0.0, 30.0)
                elif resp.status_code >= 400:
                    raise DecisionModelError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                else:
                    try:
                        payload = resp.json()
                    except ValueError as e:
                        raise DecisionModelError(f"Invalid JSON response: {resp.text[:200]}") from e
                    answer = parse_response(payload)
                    answer.latency_ms = (time.perf_counter() - started) * 1000
                    answer.attempts = attempt
                    if answer.input_tokens == 0:
                        answer.input_tokens = estimate_request_tokens(state, instructions, labels)
                        answer.tokens_estimated = True
                    return answer
            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(max(retry_after, 0.5 * 2 ** (attempt - 1)))
        raise DecisionModelError(f"Request failed after {_MAX_ATTEMPTS} attempts: {last_error}")


def test_decision_provider(provider: Provider, model: Optional[str] = None) -> str:
    """Make one tiny decision call; return the chosen option or raise.

    Text-classifier providers are tested with a single classification.
    """
    model_name = model or provider.default_decision_model or (provider.decision_models or [None])[0]
    if not model_name:
        raise DecisionModelError("No decision model configured for this provider")
    from app.services.text_classifiers import CLASSIFIER_PROVIDER_TYPES, test_classifier_provider

    if provider.provider_type in CLASSIFIER_PROVIDER_TYPES:
        return test_classifier_provider(provider, model_name)
    client = SystemOneClient(provider, model_name, timeout=30)
    labels = [
        {"name": "billing", "description": "Payments, invoices, refunds"},
        {"name": "technical", "description": "Bugs, outages, integrations"},
    ]

    async def _run() -> DecisionAnswer:
        async with client.new_http_client(1) as http:
            return await client.decide(http, "I was charged twice this month.", "Which team should handle this ticket?", labels)

    answer = asyncio.run(_run())
    if not answer.choice:
        raise DecisionModelError("Endpoint answered without a choice")
    return answer.choice
