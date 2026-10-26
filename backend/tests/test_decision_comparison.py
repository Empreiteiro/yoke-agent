"""Tests for the Model Comparison workbench (decision models vs. LLMs)."""

import asyncio
import importlib
import json
import pkgutil
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.models
from app.core.database import Base, SessionLocal, engine
from app.models.decision import DecisionDataset, DecisionPrediction
from app.models.provider import Provider
from app.services import decision_comparison as engine_mod
from app.services.decision_comparison import Outcome, compute_metrics, select_items
from app.services.decision_datasets import DatasetParseError, parse_dataset, seed_builtin_datasets
from app.services.decision_models import (
    DecisionClient, build_openai_request, build_request, parse_response, resolve_endpoint,
)
from app.services.llm_classifier import parse_answer

# Register every table (token_usage_logs has FKs into the experiment tables).
for _mod in pkgutil.iter_modules(app.models.__path__):
    importlib.import_module(f"app.models.{_mod.name}")

LABELS = [
    {"name": "billing", "description": "Payments and invoices"},
    {"name": "technical", "description": "Bugs and outages"},
]


# ── System One client ───────────────────────────────────────────────────


def test_build_request_uses_choice_question_with_criteria():
    body = build_request("jev-latest", "charged twice", "Which team?", LABELS)
    question = body["questions"]["decision"]
    assert body["model"] == "jev-latest"
    assert body["state"] == "charged twice"
    assert question["type"] == "choice"
    assert question["criteria"] == {"billing": "Payments and invoices", "technical": "Bugs and outages"}


def test_parse_response_reads_choice_probabilities_and_usage():
    answer = parse_response({
        "model": "jev-1",
        "answers": {"decision": {"choice": "billing", "probabilities": {"billing": 0.9, "technical": 0.1}}},
        "usage": {"input_tokens": 42, "output_tokens": 0},
    })
    assert answer.choice == "billing"
    assert answer.confidence == pytest.approx(0.9)
    assert answer.input_tokens == 42


def test_parse_response_falls_back_to_argmax_and_alternate_keys():
    answer = parse_response({"decisions": [{"scores": {"billing": 0.2, "technical": 0.8}}]})
    assert answer.choice == "technical"
    assert answer.confidence == pytest.approx(0.8)


def test_resolve_endpoint_variants():
    def prov(ptype, base=None, extra=None):
        return SimpleNamespace(provider_type=ptype, base_url=base, extra_config=extra or {}, name="p")

    assert resolve_endpoint(prov("typesafe")) == "https://api.typesafe.ai/v1/systemone"
    assert resolve_endpoint(prov("systemone", "http://proxy:4000/typesafe/")) == "http://proxy:4000/typesafe/v1/systemone"
    assert resolve_endpoint(prov("systemone", "http://h/v1/systemone")) == "http://h/v1/systemone"
    assert resolve_endpoint(prov("systemone", "http://h", {"path": "/decide"})) == "http://h/decide"


def test_system_one_client_sends_bearer_and_retries_429():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": "slow down"})
        body = json.loads(request.content)
        assert body["questions"]["decision"]["criteria"].keys() == {"billing", "technical"}
        return httpx.Response(200, json={"answers": {"decision": {"choice": "billing", "confidence": 0.97}}})

    provider = SimpleNamespace(provider_type="typesafe", base_url=None, extra_config={}, api_key="ts-key", name="TS")
    client = DecisionClient(provider, "jev-latest")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), headers=client.headers) as http:
            return await client.decide(http, "charged twice", "Which team?", LABELS)

    answer = asyncio.run(run())
    assert answer.choice == "billing"
    assert answer.tokens_estimated  # no usage block → char/4 estimate
    assert calls[-1].headers["authorization"] == "Bearer ts-key"
    assert len(calls) == 2


# ── OpenAI Decisions API ────────────────────────────────────────────────


def test_build_openai_request_uses_named_choice_question():
    body = build_openai_request("gpt-6-luna", "charged twice", "Which team?", LABELS)
    assert body["model"] == "gpt-6-luna"
    assert body["input"] == "charged twice"
    (question,) = body["questions"]
    assert question == {
        "type": "choice",
        "name": "decision",
        "instructions": "Which team?",
        "choices": [
            {"value": "billing", "description": "Payments and invoices"},
            {"value": "technical", "description": "Bugs and outages"},
        ],
    }


def test_parse_response_reads_openai_answer_list():
    answer = parse_response({
        "answers": [
            {"type": "predicate", "name": "other", "probability": 0.2},
            {"type": "choice", "name": "decision", "choice": "billing",
             "probabilities": [{"value": "billing", "probability": 0.95},
                               {"value": "technical", "probability": 0.05}],
             "confidence": 0.93},
        ],
        "usage": {"input_tokens": 91, "output_tokens": 0},
    })
    assert answer.choice == "billing"
    assert answer.confidence == pytest.approx(0.93)
    assert answer.probabilities == {"billing": 0.95, "technical": 0.05}
    assert answer.input_tokens == 91 and answer.refusal is None


def test_parse_response_reports_refusal_without_a_choice():
    answer = parse_response({
        "answers": [{"type": "refusal", "name": "decision", "refusal": "Unsafe request"}],
        "usage": {"input_tokens": 12},
    })
    assert answer.choice is None
    assert answer.refusal == "Unsafe request"
    assert answer.input_tokens == 12


def test_resolve_endpoint_for_openai():
    def prov(base=None):
        return SimpleNamespace(provider_type="openai", base_url=base, extra_config={}, name="OpenAI")

    assert resolve_endpoint(prov()) == "https://api.openai.com/v1/decisions"
    assert resolve_endpoint(prov("http://gateway/v1/")) == "http://gateway/v1/decisions"
    assert resolve_endpoint(prov("http://gateway/v1/decisions")) == "http://gateway/v1/decisions"


def test_decision_client_calls_openai_decisions_api():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = json.loads(request.content)
        assert body["questions"][0]["choices"][1]["value"] == "technical"
        return httpx.Response(200, json={
            "answers": [{"type": "choice", "name": "decision", "choice": "technical",
                         "probabilities": {"billing": 0.1, "technical": 0.9}}],
            "usage": {"input_tokens": 64, "output_tokens": 3},
        })

    provider = SimpleNamespace(provider_type="openai", base_url=None, extra_config={}, api_key="sk-test", name="OpenAI")
    client = DecisionClient(provider, "gpt-6-luna")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), headers=client.headers) as http:
            return await client.decide(http, "app crashes", "Which team?", LABELS)

    answer = asyncio.run(run())
    assert str(seen[0].url) == "https://api.openai.com/v1/decisions"
    assert seen[0].headers["authorization"] == "Bearer sk-test"
    assert answer.choice == "technical"
    assert answer.confidence == pytest.approx(0.9)
    assert (answer.input_tokens, answer.tokens_estimated) == (64, False)


def test_openai_decision_pricing_differs_from_llm_pricing():
    provider = SimpleNamespace(provider_type="openai", extra_config={})
    assert engine_mod.default_prices("decision", provider, "gpt-6-luna") == (0.10, 0.0, "OpenAI list price")
    assert engine_mod.default_prices("llm", provider, "gpt-6-luna")[:2] == (0.10, 0.50)
    assert engine_mod.default_prices("decision", provider, "gpt-7-nova") == (None, None, "unknown")
    typesafe = SimpleNamespace(provider_type="typesafe", extra_config={})
    assert engine_mod.default_prices("decision", typesafe, "jev-1.13.0") == (0.042, 0.0, "TypeSafe list price")


# ── LLM answer parsing ──────────────────────────────────────────────────


@pytest.mark.parametrize("content,expected", [
    ('{"label": "billing", "confidence": 0.8}', ("billing", 0.8)),
    ('```json\n{"label": "Technical"}\n```', ("technical", None)),
    ('Sure! {"label": "billing"} hope that helps', ("billing", None)),
    ("billing", ("billing", None)),
    ("The answer is technical.", ("technical", None)),
    ("Could be billing or technical", (None, None)),
    ('{"label": "shipping"}', (None, None)),
])
def test_parse_answer(content, expected):
    assert parse_answer(content, ["billing", "technical"]) == expected


# ── Sampling & metrics ──────────────────────────────────────────────────


def test_stratified_sampling_preserves_distribution_and_is_deterministic():
    items = [(i, "a") for i in range(1, 801)] + [(i, "b") for i in range(801, 1001)]
    first = select_items(items, 100, "stratified", seed=7)
    assert first == select_items(items, 100, "stratified", seed=7)
    labels = dict(items)
    assert sum(1 for i in first if labels[i] == "a") == 80
    assert sum(1 for i in first if labels[i] == "b") == 20
    assert select_items(items, None) == list(range(1, 1001))
    assert select_items(items, 5, "first") == [1, 2, 3, 4, 5]


def _pred(expected, predicted, status="ok", conf=None, latency=10.0, cost=0.001):
    return SimpleNamespace(
        expected_label=expected, predicted_label=predicted, status=status,
        is_correct=status == "ok" and expected == predicted, confidence=conf,
        latency_ms=latency, input_tokens=10, output_tokens=2, cost=cost,
    )


def test_compute_metrics_counts_correct_incorrect_failed():
    preds = [
        _pred("billing", "billing", conf=0.9),
        _pred("billing", "technical", conf=0.6),
        _pred("technical", "technical", conf=0.8),
        _pred("technical", None, status="error", latency=None, cost=None),
    ]
    m = compute_metrics(preds, ["billing", "technical"])
    assert (m["total"], m["correct"], m["incorrect"], m["failed"]) == (4, 2, 1, 1)
    assert m["accuracy"] == pytest.approx(0.5)
    assert m["per_label"]["billing"]["recall"] == pytest.approx(0.5)
    assert m["per_label"]["technical"]["precision"] == pytest.approx(0.5)
    assert m["confusion"]["technical"]["(no answer)"] == 1
    assert m["total_cost"] == pytest.approx(0.003)
    assert m["avg_confidence_correct"] == pytest.approx(0.85)


# ── Dataset upload parsing ──────────────────────────────────────────────


def test_parse_csv_detects_columns_and_dedupes():
    csv_bytes = (
        "message,category\n"
        '"Charged twice, please fix",billing\n'
        "App crashes on login,technical\n"
        "App crashes on login,technical\n"
        ",billing\n"
    ).encode()
    parsed = parse_dataset("tickets.csv", csv_bytes, label_descriptions={"billing": "Money stuff"})
    assert (parsed["text_column"], parsed["label_column"]) == ("message", "category")
    assert parsed["rows_valid"] == 2
    assert parsed["labels"][0] == {"name": "billing", "description": "Money stuff"}
    assert any("duplicate" in w for w in parsed["warnings"])


def test_preview_without_detectable_columns_asks_for_mapping():
    content = b"message,team\nCharged twice,billing\nApp crashes,tech\n"
    preview = parse_dataset("t.csv", content, allow_unmapped=True)
    assert preview["needs_mapping"] and preview["label_column"] is None
    assert preview["text_column"] == "message"
    assert preview["raw_sample"][0] == {"message": "Charged twice", "team": "billing"}
    mapped = parse_dataset("t.csv", content, label_column="team")
    assert mapped["rows_valid"] == 2
    with pytest.raises(DatasetParseError, match="label column"):
        parse_dataset("t.csv", content)


def test_parse_json_export_format_validates_declared_labels():
    payload = {"task": "Which team?", "labels": LABELS, "items": [
        {"text": "x", "label": "billing"}, {"text": "y", "label": "shipping"},
    ]}
    with pytest.raises(DatasetParseError, match="not declared"):
        parse_dataset("d.json", json.dumps(payload).encode())


def test_parse_rejects_single_label():
    with pytest.raises(DatasetParseError, match="at least 2"):
        parse_dataset("d.jsonl", b'{"text": "a", "label": "x"}\n{"text": "b", "label": "x"}\n')


def test_builtin_datasets_have_at_least_1000_rows():
    from app.services.decision_datasets import BUILTIN_DIR

    files = sorted(BUILTIN_DIR.glob("*.json"))
    assert files, "built-in datasets missing — run scripts/generate_decision_datasets.py"
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data["items"]) >= 1000, path.name
        names = {l["name"] for l in data["labels"]}
        assert {i["label"] for i in data["items"]} <= names, path.name


# ── API end-to-end (fake classifiers) ───────────────────────────────────


class _FakeClassifier:
    """Answers 'billing' for texts mentioning money, else 'technical'."""

    def __init__(self, kind):
        self.kind = kind

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def classify(self, text):
        if self.kind == "broken":
            raise RuntimeError("401 unauthorized")
        label = "billing" if ("charge" in text or "invoice" in text) else "technical"
        if self.kind == "llm" and "invoice" in text:
            label = "technical"  # the LLM gets invoices wrong
        return Outcome(predicted=label, confidence=0.9, input_tokens=100, output_tokens=10, latency_ms=5.0)


@pytest.fixture()
def client(monkeypatch):
    from app.api import decision as decision_api

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add_all([
        Provider(id=1, name="TypeSafe", provider_type="typesafe", api_key="k", is_active=True,
                 supports_decision=True, decision_models=["jev-latest"]),
        Provider(id=2, name="OpenAI", provider_type="openai", api_key="k", is_active=True,
                 supports_llm=True, llm_models=["gpt-4o-mini"]),
        Provider(id=3, name="Broken", provider_type="systemone", base_url="http://x", is_active=True,
                 supports_decision=True, decision_models=["open-jev"]),
    ])
    db.commit()
    db.close()

    def fake_build(db, result, comp, concurrency):
        kind = "broken" if result.provider_id == 3 else result.kind
        return _FakeClassifier(kind)

    monkeypatch.setattr(engine_mod, "_build_classifier", fake_build)
    app = FastAPI()
    app.include_router(decision_api.router, prefix="/api/decision")
    with TestClient(app) as c:
        yield c


def _upload(client):
    rows = []
    for i in range(30):
        rows.append({"text": f"I was charged twice #{i}", "label": "billing"})
        rows.append({"text": f"Where is invoice {i}?", "label": "billing"})
        rows.append({"text": f"The app crashes on screen {i}", "label": "technical"})
    payload = {"task": "Which team should handle this?", "labels": LABELS, "items": rows}
    res = client.post(
        "/api/decision/datasets/upload",
        files={"file": ("tickets.json", json.dumps(payload), "application/json")},
        data={"name": "Tickets"},
    )
    assert res.status_code == 200, res.text
    return res.json()["dataset"]["id"]


def test_comparison_end_to_end(client):
    dataset_id = _upload(client)
    preview = client.post(
        "/api/decision/datasets/upload",
        files={"file": ("t.csv", "text,label\na,x\nb,y\n", "text/csv")},
        data={"dry_run": "true"},
    ).json()
    assert preview["dry_run"] and preview["rows_valid"] == 2

    estimate = client.post("/api/decision/comparisons/estimate", json={
        "dataset_id": dataset_id,
        "models": [{"kind": "decision", "provider_id": 1, "model": "jev-latest"}],
        "sample_size": 30,
    }).json()
    assert estimate["items"] == 30
    assert estimate["models"][0]["input_price_per_million"] == pytest.approx(0.042)

    res = client.post("/api/decision/comparisons", json={
        "dataset_id": dataset_id,
        "sample_size": 60,
        "models": [
            {"kind": "decision", "provider_id": 1, "model": "jev-latest"},
            {"kind": "llm", "provider_id": 2, "model": "gpt-4o-mini"},
            {"kind": "decision", "provider_id": 3, "model": "open-jev", "input_price_per_million": 0},
        ],
    })
    assert res.status_code == 201, res.text
    comp_id = res.json()["id"]

    # TestClient runs BackgroundTasks before returning, so the run is done.
    detail = client.get(f"/api/decision/comparisons/{comp_id}").json()
    assert detail["status"] == "completed"
    by_name = {m["model_name"]: m for m in detail["models"]}

    jev = by_name["jev-latest"]
    assert (jev["total"], jev["correct"], jev["incorrect"], jev["failed"]) == (60, 60, 0, 0)
    assert jev["accuracy"] == 1.0 and jev["rank"] == 1
    assert jev["total_cost"] == pytest.approx(60 * 100 * 0.042 / 1e6)

    llm = by_name["gpt-4o-mini"]
    assert llm["correct"] + llm["incorrect"] == 60 and llm["incorrect"] > 0
    assert llm["error_rate"] == pytest.approx(llm["incorrect"] / 60)
    assert llm["total_cost"] == pytest.approx(60 * (100 * 0.15 + 10 * 0.60) / 1e6)
    assert llm["cost_vs_cheapest"] > 1

    broken = by_name["open-jev"]
    assert broken["status"] == "failed"
    assert "consecutive errors" in broken["error_message"]

    preds = client.get(f"/api/decision/comparisons/{comp_id}/predictions",
                       params={"model_result_id": llm["id"], "outcome": "incorrect"}).json()
    assert preds["total"] == llm["incorrect"]
    assert all(p["expected_label"] == "billing" and p["predicted_label"] == "technical" for p in preds["items"])

    csv_text = client.get(f"/api/decision/comparisons/{comp_id}/export").text
    assert csv_text.splitlines()[0].startswith("item_id,text,expected_label")
    assert len(csv_text.strip().splitlines()) == 61

    # Resuming retries the broken model's errored rows.
    assert client.post(f"/api/decision/comparisons/{comp_id}/resume").status_code == 200

    assert client.delete(f"/api/decision/datasets/{dataset_id}").json()["deleted_comparisons"] == 1
    db = SessionLocal()
    assert db.query(DecisionPrediction).count() == 0
    db.close()


def test_openai_provider_lists_decision_and_llm_variants(client):
    db = SessionLocal()
    openai = db.query(Provider).filter(Provider.id == 2).first()
    openai.llm_models = ["gpt-6-luna"]
    openai.supports_decision = True
    openai.decision_models = ["gpt-6-luna"]
    db.commit()
    db.close()

    models = client.get("/api/decision/models").json()
    decision = next(m for m in models["decision_models"] if m["provider_id"] == 2)
    llm = next(m for m in models["llm_models"] if m["provider_id"] == 2)
    assert decision["display_name"] == "gpt-6-luna · Decisions (OpenAI)"
    assert llm["display_name"] == "gpt-6-luna (OpenAI)"
    assert (decision["input_price_per_million"], decision["output_price_per_million"]) == (0.10, 0.0)
    assert decision["pricing_source"] == "OpenAI list price"

    dataset_id = _upload(client)
    estimate = client.post("/api/decision/comparisons/estimate", json={
        "dataset_id": dataset_id,
        "models": [
            {"kind": "decision", "provider_id": 2, "model": "gpt-6-luna"},
            {"kind": "llm", "provider_id": 2, "model": "gpt-6-luna"},
        ],
        "sample_size": 10,
    })
    assert estimate.status_code == 200, estimate.text
    names = [m["display_name"] for m in estimate.json()["models"]]
    assert names == ["gpt-6-luna · Decisions (OpenAI)", "gpt-6-luna (OpenAI)"]


def test_builtin_datasets_are_read_only(client):
    db = SessionLocal()
    seed_builtin_datasets(db)
    builtin = db.query(DecisionDataset).filter(DecisionDataset.is_builtin.is_(True)).first()
    db.close()
    assert builtin is not None
    assert client.delete(f"/api/decision/datasets/{builtin.id}").status_code == 403
    copy = client.post(f"/api/decision/datasets/{builtin.id}/duplicate").json()
    assert copy["item_count"] == builtin.item_count and not copy["is_builtin"]
    labels = [{**l, "description": "edited"} for l in copy["labels"]]
    assert client.put(f"/api/decision/datasets/{copy['id']}", json={"labels": labels}).status_code == 200
    bad = labels[:-1]
    assert client.put(f"/api/decision/datasets/{copy['id']}", json={"labels": bad}).status_code == 400
