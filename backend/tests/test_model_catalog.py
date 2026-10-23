"""Provider model catalog, price table and per-model request settings."""

import importlib
import pkgutil
from datetime import date

import pytest

import app.models
from app.core.database import Base, SessionLocal, engine
from app.models.provider import Provider
from app.schemas.provider import PROVIDER_CATALOG
from app.services.llm_factory import (
    anthropic_accepts_temperature, flex_supported_for, get_llm, is_openai_reasoning_model,
)
from app.services.token_tracker import estimate_cost, lookup_pricing

for _mod in pkgutil.iter_modules(app.models.__path__):
    importlib.import_module(f"app.models.{_mod.name}")


@pytest.mark.parametrize("ptype", ["openai", "anthropic", "google"])
def test_every_catalog_llm_model_has_a_price(ptype):
    missing = [m for m in PROVIDER_CATALOG[ptype]["llm_models"] if lookup_pricing(m) is None]
    assert missing == []


def test_retired_models_left_the_catalog():
    models = {m for p in ("openai", "anthropic", "google") for m in PROVIDER_CATALOG[p]["llm_models"]}
    for retired in ("o4-mini", "o3-mini", "gpt-4.1-nano", "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229", "gemini-2.0-flash", "gemini-1.5-pro"):
        assert retired not in models


def test_lookup_prefers_the_most_specific_key():
    assert lookup_pricing("gpt-4o-mini-2024-07-18") == {"prompt": 0.15, "completion": 0.60}
    # Used to fall through to the legacy "claude-opus-4" ($15 / $75) entry.
    assert lookup_pricing("claude-opus-4-8") == {"prompt": 5.00, "completion": 25.00}
    assert lookup_pricing("gemini-3.5-flash-lite-001") == {"prompt": 0.30, "completion": 2.50}
    # A bare family name matches several keys — ambiguous, so unpriced.
    assert lookup_pricing("gpt-6") is None


@pytest.mark.parametrize("model,before,after,switch", [
    ("gemini-4-argon", (2.00, 10.00), (4.00, 20.00), date(2026, 12, 1)),
    ("gemini-3.8-flash", (0.75, 3.75), (1.50, 7.50), date(2027, 1, 1)),
    ("gpt-5.6-sol", (4.00, 20.00), (5.00, 30.00), date(2026, 11, 21)),
])
def test_scheduled_price_changes_apply_on_their_date(model, before, after, switch):
    day_before = date.fromordinal(switch.toordinal() - 1)
    assert lookup_pricing(model, on=day_before) == {"prompt": before[0], "completion": before[1]}
    assert lookup_pricing(model, on=switch) == {"prompt": after[0], "completion": after[1]}


def test_estimate_cost_uses_new_prices():
    assert estimate_cost("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.60)
    assert estimate_cost("gpt-6-luna", 2_000_000, 0) == pytest.approx(0.20)


@pytest.mark.parametrize("model,accepts", [
    ("claude-opus-5-5", False), ("claude-sonnet-5-5", False), ("claude-haiku-5-5", False),
    ("claude-fable-5-1", False), ("claude-opus-4-7", False), ("claude-sonnet-5", False),
    ("claude-opus-4-6", True), ("claude-sonnet-4-6", True), ("claude-haiku-4-5", True),
    ("claude-sonnet-4-20250514", True), ("claude-3-haiku-20240307", True),
])
def test_anthropic_sampling_support(model, accepts):
    assert anthropic_accepts_temperature(model) is accepts


def test_openai_reasoning_and_flex_rules():
    for model in ("gpt-5.5", "gpt-5.4-mini", "gpt-6.1-sol", "gpt-6-luna", "o3"):
        assert is_openai_reasoning_model(model)
        assert flex_supported_for("openai", model)
    assert not is_openai_reasoning_model("gpt-4.1")
    assert not flex_supported_for("openai", "gpt-4.1")
    assert flex_supported_for("google", "gemini-3.8-flash")
    assert not flex_supported_for("google", "gemini-4-argon")


@pytest.fixture()
def providers():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    rows = [
        Provider(name="Anthropic test", provider_type="anthropic", api_key="sk-ant-test",
                 is_active=True, supports_llm=True, llm_models=PROVIDER_CATALOG["anthropic"]["llm_models"]),
        Provider(name="OpenAI test", provider_type="openai", api_key="sk-test", is_active=True,
                 supports_llm=True, llm_models=PROVIDER_CATALOG["openai"]["llm_models"],
                 extra_config={"flex_tier": True}),
    ]
    db.add_all(rows)
    db.commit()
    ids = {p.provider_type: p.id for p in rows}
    yield db, ids
    for p in rows:
        db.delete(p)
    db.commit()
    db.close()


def test_get_llm_omits_temperature_where_models_reject_it(providers):
    db, ids = providers
    assert get_llm(db, provider_id=ids["anthropic"], model="claude-opus-5-5", temperature=0).temperature is None
    assert get_llm(db, provider_id=ids["anthropic"], model="claude-sonnet-4-6", temperature=0).temperature == 0
    gpt = get_llm(db, provider_id=ids["openai"], model="gpt-6.1-sol", temperature=0)
    assert gpt.temperature is None
    assert gpt.service_tier == "flex"
