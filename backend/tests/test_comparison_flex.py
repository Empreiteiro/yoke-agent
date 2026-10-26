"""Per-model flex service tier in Model Comparison."""

import importlib
import json
import pkgutil
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.models
from app.core.database import Base, SessionLocal, engine
from app.models.decision import DecisionModelResult
from app.models.provider import Provider
from app.services import decision_comparison as engine_mod
from app.services.llm_factory import get_llm, uses_flex

for _mod in pkgutil.iter_modules(app.models.__path__):
    importlib.import_module(f"app.models.{_mod.name}")

LABELS = [
    {"name": "billing", "description": "Payments and invoices"},
    {"name": "technical", "description": "Bugs and outages"},
]


def _openai(flex_tier=False):
    return SimpleNamespace(provider_type="openai", extra_config={"flex_tier": flex_tier})


def test_uses_flex_follows_the_override_then_the_provider():
    assert uses_flex(_openai(False), "gpt-6.1-sol", True)
    assert not uses_flex(_openai(True), "gpt-6.1-sol", False)
    assert uses_flex(_openai(True), "gpt-6.1-sol")
    assert not uses_flex(_openai(False), "gpt-6.1-sol")
    # Models without a flex tier never get it.
    assert not uses_flex(_openai(True), "gpt-4o", True)


def test_default_prices_honour_the_flex_choice():
    standard = engine_mod.default_prices("llm", _openai(False), "gpt-6.1-sol")
    flex = engine_mod.default_prices("llm", _openai(False), "gpt-6.1-sol", flex=True)
    assert standard == (2.00, 10.00, "price table")
    assert flex == (1.00, 5.00, "price table (flex tier)")
    assert engine_mod.default_prices("llm", _openai(True), "gpt-6.1-sol", flex=False) == standard
    assert engine_mod.default_prices("llm", _openai(True), "gpt-4o", flex=True)[2] == "price table"


@pytest.fixture()
def db_providers():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add_all([
        Provider(id=1, name="OpenAI", provider_type="openai", api_key="sk-test", is_active=True,
                 supports_llm=True, llm_models=["gpt-6.1-sol", "gpt-4o"], extra_config={"flex_tier": False}),
        Provider(id=2, name="Gemini", provider_type="google", api_key="g-test", is_active=True,
                 supports_llm=True, llm_models=["gemini-3.8-flash"], extra_config={"flex_tier": True}),
    ])
    db.commit()
    yield db
    db.close()


def test_get_llm_flex_override(db_providers):
    db = db_providers
    assert get_llm(db, provider_id=1, model="gpt-6.1-sol").service_tier is None
    assert get_llm(db, provider_id=1, model="gpt-6.1-sol", flex=True).service_tier == "flex"
    assert get_llm(db, provider_id=1, model="gpt-4o", flex=True).service_tier is None
    # Gemini's provider has flex on; a per-call False turns it off.
    assert get_llm(db, provider_id=2, model="gemini-3.8-flash").kwargs == {"service_tier": "flex"}
    assert not hasattr(get_llm(db, provider_id=2, model="gemini-3.8-flash", flex=False), "kwargs")


def test_llm_classifier_waits_longer_on_flex(db_providers):
    db = db_providers
    provider = db.get(Provider, 1)
    flex = engine_mod._LLMClassifier(db, provider, "gpt-6.1-sol", "t", LABELS, 0.0, {"flex": True})
    standard = engine_mod._LLMClassifier(db, provider, "gpt-6.1-sol", "t", LABELS, 0.0, {})
    assert flex.llm.service_tier == "flex" and flex.timeout == engine_mod.FLEX_CALL_TIMEOUT_S
    assert standard.llm.service_tier is None and standard.timeout == engine_mod.LLM_CALL_TIMEOUT_S


@pytest.fixture()
def client(db_providers):
    from app.api import decision as decision_api

    app = FastAPI()
    app.include_router(decision_api.router, prefix="/api/decision")
    with TestClient(app) as c:
        yield c


def _dataset(client) -> int:
    rows = [{"text": f"I was charged twice #{i}", "label": "billing"} for i in range(10)]
    rows += [{"text": f"The app crashes #{i}", "label": "technical"} for i in range(10)]
    res = client.post(
        "/api/decision/datasets/upload",
        files={"file": ("t.json", json.dumps({"task": "Which team?", "labels": LABELS, "items": rows}), "application/json")},
        data={"name": "Tickets"},
    )
    assert res.status_code == 200, res.text
    return res.json()["dataset"]["id"]


def test_models_listing_reports_flex_support(client):
    listing = client.get("/api/decision/models").json()
    assert listing["flex_discount"] == 0.5
    by_model = {m["model"]: m for m in listing["llm_models"]}
    assert (by_model["gpt-6.1-sol"]["flex_supported"], by_model["gpt-6.1-sol"]["flex"]) == (True, False)
    assert (by_model["gpt-4o"]["flex_supported"], by_model["gpt-4o"]["flex"]) == (False, False)
    gemini = by_model["gemini-3.8-flash"]
    assert gemini["flex"] is True and gemini["pricing_source"] == "price table (flex tier)"


def test_estimate_and_create_apply_the_flex_choice(client):
    dataset_id = _dataset(client)
    models = [
        {"kind": "llm", "provider_id": 1, "model": "gpt-6.1-sol"},
        {"kind": "llm", "provider_id": 1, "model": "gpt-6.1-sol", "flex": True},
        {"kind": "llm", "provider_id": 1, "model": "gpt-4o", "flex": True},
    ]
    estimate = client.post("/api/decision/comparisons/estimate", json={"dataset_id": dataset_id, "models": models}).json()
    standard, flex, no_flex = estimate["models"]
    assert (standard["flex"], flex["flex"], no_flex["flex"]) == (False, True, None)
    assert flex["input_price_per_million"] == standard["input_price_per_million"] / 2
    assert flex["estimated_cost"] == pytest.approx(standard["estimated_cost"] / 2)
    assert flex["display_name"] == "gpt-6.1-sol (OpenAI) · flex"
    assert standard["display_name"] == "gpt-6.1-sol (OpenAI)"

    res = client.post("/api/decision/comparisons", json={
        "dataset_id": dataset_id, "models": models, "autostart": False,
    })
    assert res.status_code == 201, res.text
    db = SessionLocal()
    results = db.query(DecisionModelResult).order_by(DecisionModelResult.position).all()
    db.close()
    configs = [r.config for r in results]
    # The tier is pinned at creation; models without flex carry no choice.
    assert configs[0]["flex"] is False and configs[1]["flex"] is True and "flex" not in configs[2]
    assert results[1].input_price_per_million == 1.00 and results[1].output_price_per_million == 5.00
    assert results[1].display_name == "gpt-6.1-sol (OpenAI) · flex"
    # Flex doesn't change what the model is asked, so it isn't a policy variant.
    assert results[0].policy_hash == results[1].policy_hash
