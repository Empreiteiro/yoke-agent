"""Shared HTTP client for the Yoke Agent backend.

This module is the *single source of truth* for talking to the FastAPI
backend over HTTP. Both the MCP server (``backend/mcp_server.py``) and
the standalone CLI (``cli/yoke_cli/``) use it so the two surfaces never
drift apart.

Design notes:
- Depends only on ``httpx`` (no FastAPI / SQLAlchemy / app imports), so
  it can be safely vendored into the CLI package.
- Methods return parsed JSON (``dict`` / ``list``) — no pydantic models.
- Errors raise ``httpx.HTTPStatusError`` after ``response.raise_for_status``.
- Reads ``YOKE_BASE_URL`` / ``YOKE_API_KEY`` from the environment by
  default, with ``RAG_BASE_URL`` / ``RAG_API_KEY`` as legacy fallbacks.

If you change this file, run ``make sync-cli-client`` to refresh the
vendored copy at ``cli/yoke_cli/client.py``.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

DEFAULT_BASE_URL = "http://localhost:4040/api"


def _env_base_url() -> str:
    return (
        os.environ.get("YOKE_BASE_URL")
        or os.environ.get("RAG_BASE_URL")
        or DEFAULT_BASE_URL
    )


def _env_api_key() -> str:
    return os.environ.get("YOKE_API_KEY") or os.environ.get("RAG_API_KEY") or ""


class YokeClient:
    """Thin HTTP wrapper around the Yoke FastAPI backend."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or _env_base_url()).rstrip("/")
        self.api_key = api_key if api_key is not None else _env_api_key()
        self.timeout = timeout

    # ── plumbing ────────────────────────────────────────────────────

    def _client(self) -> httpx.Client:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return httpx.Client(
            base_url=self.base_url, timeout=self.timeout, headers=headers
        )

    def _get(self, path: str) -> Any:
        with self._client() as c:
            r = c.get(path)
            r.raise_for_status()
            return r.json()

    def _post(self, path: str, json: Optional[dict] = None) -> Any:
        with self._client() as c:
            r = c.post(path, json=json)
            r.raise_for_status()
            return r.json() if r.content else {}

    def _put(self, path: str, json: Optional[dict] = None) -> Any:
        with self._client() as c:
            r = c.put(path, json=json)
            r.raise_for_status()
            return r.json() if r.content else {}

    def _delete(self, path: str) -> Any:
        with self._client() as c:
            r = c.delete(path)
            r.raise_for_status()
            return r.json() if r.content else {"detail": "deleted"}

    # ── health / discovery ──────────────────────────────────────────

    def health(self) -> dict:
        """Lightweight liveness check (GET /providers/ — any 2xx is healthy)."""
        with self._client() as c:
            r = c.get("/providers/")
            return {
                "ok": r.is_success,
                "status_code": r.status_code,
                "base_url": self.base_url,
            }

    # ── documents ───────────────────────────────────────────────────

    def list_documents(self) -> list[dict]:
        return self._get("/documents/")

    def upload_document(self, filepath: str) -> dict:
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            with self._client() as c:
                r = c.post("/documents/upload", files={"file": (filename, f)})
                r.raise_for_status()
                return r.json()

    # ── datasets ────────────────────────────────────────────────────

    def list_datasets(self) -> list[dict]:
        return self._get("/datasets/")

    def get_dataset(self, dataset_id: int) -> dict:
        return self._get(f"/datasets/{dataset_id}")

    def create_dataset(
        self,
        document_ids: list[int],
        name: str = "",
        description: str = "",
    ) -> dict:
        return self._post(
            "/datasets/",
            json={
                "name": name or None,
                "description": description or None,
                "document_ids": document_ids,
            },
        )

    def generate_dataset(
        self,
        dataset_id: int,
        reading_mode: str = "full",
        max_pages: int = 0,
        num_questions: int = 0,
    ) -> dict:
        options: dict = {"reading_mode": reading_mode}
        if max_pages > 0:
            options["max_pages"] = max_pages
        if num_questions > 0:
            options["num_questions"] = num_questions
        return self._post(f"/datasets/{dataset_id}/generate", json=options)

    def approve_dataset(self, dataset_id: int) -> dict:
        return self._post(f"/datasets/{dataset_id}/approve")

    # ── experiments (RAG) ───────────────────────────────────────────

    def list_experiments(self) -> list[dict]:
        return self._get("/experiments/")

    def create_experiment(
        self,
        dataset_id: int,
        name: str = "",
        vectorstore_type: str = "chromadb",
    ) -> dict:
        return self._post(
            "/experiments/",
            json={
                "name": name or None,
                "dataset_id": dataset_id,
                "vectorstore_type": vectorstore_type,
            },
        )

    def configure_grid_search(
        self,
        experiment_id: int,
        chunk_sizes: Optional[list[int]] = None,
        chunk_overlaps: Optional[list[int]] = None,
        embedding_models: Optional[list[str]] = None,
        top_k_values: Optional[list[int]] = None,
        search_types: Optional[list[str]] = None,
        distance_metrics: Optional[list[str]] = None,
        embedding_dimensions: Optional[list[int]] = None,
    ) -> dict:
        return self._post(
            f"/experiments/{experiment_id}/configure-grid",
            json={
                "chunk_sizes": chunk_sizes or [512, 1024],
                "chunk_overlaps": chunk_overlaps or [10, 20],
                "embedding_models": embedding_models or ["text-embedding-3-small"],
                "top_k_values": top_k_values or [3, 5],
                "search_types": search_types or ["vector"],
                "distance_metrics": distance_metrics or ["cosine"],
                "embedding_dimensions": embedding_dimensions or [],
            },
        )

    def run_experiment(self, experiment_id: int) -> dict:
        return self._post(f"/experiments/{experiment_id}/run")

    def stop_experiment(self, experiment_id: int) -> dict:
        return self._post(f"/experiments/{experiment_id}/stop")

    def resume_experiment(self, experiment_id: int, retry_failed: bool = False) -> dict:
        return self._post(
            f"/experiments/{experiment_id}/resume?retry_failed={str(retry_failed).lower()}"
        )

    def get_experiment(self, experiment_id: int) -> dict:
        return self._get(f"/experiments/{experiment_id}")

    def get_experiment_report(self, experiment_id: int) -> dict:
        return self._get(f"/experiments/{experiment_id}/report")

    def delete_experiment(self, experiment_id: int) -> dict:
        return self._delete(f"/experiments/{experiment_id}")

    # ── collections ─────────────────────────────────────────────────

    def list_collections(self) -> list[dict]:
        return self._get("/collections/")

    def query_collection(
        self, collection_id: int, question: str, top_k: int = 0
    ) -> dict:
        data: dict = {"question": question}
        if top_k > 0:
            data["top_k"] = top_k
        return self._post(f"/collections/{collection_id}/query", json=data)

    def delete_collection(self, collection_id: int) -> dict:
        return self._delete(f"/collections/{collection_id}")

    # ── providers ───────────────────────────────────────────────────

    def list_providers(self) -> list[dict]:
        return self._get("/providers/")

    def get_available_models(self) -> dict:
        return self._get("/providers/models/available")

    def get_provider_catalog(self) -> dict:
        return self._get("/providers/catalog")

    def get_provider(self, provider_id: int) -> dict:
        return self._get(f"/providers/{provider_id}")

    def create_provider(
        self,
        name: str,
        provider_type: str,
        api_key: str = "",
        base_url: str = "",
        llm_models: Optional[list[str]] = None,
        embedding_models: Optional[list[str]] = None,
        default_llm_model: str = "",
        default_embedding_model: str = "",
        supports_llm: bool = True,
        supports_embedding: bool = False,
        extra_config: Optional[dict] = None,
    ) -> dict:
        payload = {
            "name": name,
            "provider_type": provider_type,
            "api_key": api_key or None,
            "base_url": base_url or None,
            "llm_models": llm_models or [],
            "embedding_models": embedding_models or [],
            "default_llm_model": default_llm_model or None,
            "default_embedding_model": default_embedding_model or None,
            "supports_llm": supports_llm,
            "supports_embedding": supports_embedding,
            "extra_config": extra_config or {},
        }
        return self._post("/providers/", json=payload)

    def update_provider(
        self,
        provider_id: int,
        name: str = "",
        api_key: str = "",
        base_url: str = "",
        llm_models: Optional[list[str]] = None,
        embedding_models: Optional[list[str]] = None,
        default_llm_model: str = "",
        default_embedding_model: str = "",
        is_active: Optional[bool] = None,
        extra_config: Optional[dict] = None,
    ) -> dict:
        payload: dict = {}
        if name:
            payload["name"] = name
        if api_key:
            payload["api_key"] = api_key
        if base_url:
            payload["base_url"] = base_url
        if llm_models is not None:
            payload["llm_models"] = llm_models
        if embedding_models is not None:
            payload["embedding_models"] = embedding_models
        if default_llm_model:
            payload["default_llm_model"] = default_llm_model
        if default_embedding_model:
            payload["default_embedding_model"] = default_embedding_model
        if is_active is not None:
            payload["is_active"] = is_active
        if extra_config is not None:
            payload["extra_config"] = extra_config
        return self._put(f"/providers/{provider_id}", json=payload)

    def delete_provider(self, provider_id: int) -> dict:
        return self._delete(f"/providers/{provider_id}")

    def test_provider(self, provider_id: int) -> dict:
        return self._post(f"/providers/{provider_id}/test")

    # ── agent workbench: configs ────────────────────────────────────

    def list_agent_configs(self) -> list[dict]:
        return self._get("/agent/configs/")

    def get_agent_config(self, config_id: int) -> dict:
        return self._get(f"/agent/configs/{config_id}")

    def create_agent_config(
        self,
        name: str,
        system_prompt: str,
        description: str = "",
        tools: Optional[list[dict]] = None,
        constraints: Optional[list[str]] = None,
    ) -> dict:
        payload = {
            "name": name,
            "system_prompt": system_prompt,
            "description": description or None,
            "tools": tools or [],
            "constraints": constraints or [],
        }
        return self._post("/agent/configs/", json=payload)

    def update_agent_config(
        self,
        config_id: int,
        name: str = "",
        description: str = "",
        system_prompt: str = "",
        tools: Optional[list[dict]] = None,
        constraints: Optional[list[str]] = None,
    ) -> dict:
        payload: dict = {}
        if name:
            payload["name"] = name
        if description:
            payload["description"] = description
        if system_prompt:
            payload["system_prompt"] = system_prompt
        if tools is not None:
            payload["tools"] = tools
        if constraints is not None:
            payload["constraints"] = constraints
        return self._put(f"/agent/configs/{config_id}", json=payload)

    def delete_agent_config(self, config_id: int) -> dict:
        return self._delete(f"/agent/configs/{config_id}")

    # ── agent workbench: prompt variants ────────────────────────────

    def list_prompt_variants(self, config_id: int) -> list[dict]:
        return self._get(f"/agent/configs/{config_id}/variants")

    def generate_prompt_variants(
        self, config_id: int, count: int = 3, focus: str = ""
    ) -> list[dict]:
        return self._post(
            f"/agent/configs/{config_id}/variants/generate",
            json={"count": count, "focus": focus or None},
        )

    # ── agent workbench: scenarios ──────────────────────────────────

    def list_scenarios(self, config_id: int) -> list[dict]:
        return self._get(f"/agent/configs/{config_id}/scenarios")

    def generate_scenarios(
        self,
        config_id: int,
        scenario_type: str = "response_quality",
        count: int = 5,
    ) -> list[dict]:
        return self._post(
            f"/agent/configs/{config_id}/scenarios/generate",
            json={"scenario_type": scenario_type, "count": count},
        )

    # ── agent workbench: personas ───────────────────────────────────

    def list_personas(self, config_id: int) -> list[dict]:
        return self._get(f"/agent/configs/{config_id}/personas")

    def generate_personas(
        self,
        config_id: int,
        audience_description: str,
        count: int = 5,
        interaction_count: int = 10,
    ) -> list[dict]:
        return self._post(
            f"/agent/configs/{config_id}/personas/generate",
            json={
                "audience_description": audience_description,
                "count": count,
                "interaction_count": interaction_count,
            },
        )

    # ── agent workbench: experiments ────────────────────────────────

    def list_agent_experiments(self) -> list[dict]:
        return self._get("/agent/experiments")

    def get_agent_experiment(self, experiment_id: int) -> dict:
        return self._get(f"/agent/experiments/{experiment_id}")

    def create_agent_experiment(
        self,
        name: str,
        agent_config_id: int,
        prompt_variant_ids: list[int],
        llm_models: list[str],
        temperatures: Optional[list[float]] = None,
        persona_group_names: Optional[list[str]] = None,
        scenario_types: Optional[list[str]] = None,
        max_turns: Optional[list[int]] = None,
        description: str = "",
    ) -> dict:
        grid_config = {
            "prompt_variant_ids": prompt_variant_ids,
            "llm_models": llm_models,
            "temperatures": temperatures or [0.0],
            "persona_group_names": persona_group_names or [],
            "scenario_types": scenario_types or [],
            "max_turns": max_turns or [1],
        }
        payload = {
            "name": name,
            "agent_config_id": agent_config_id,
            "description": description or None,
            "grid_config": grid_config,
        }
        return self._post("/agent/experiments", json=payload)

    def run_agent_experiment(self, experiment_id: int) -> dict:
        return self._post(f"/agent/experiments/{experiment_id}/run")

    def stop_agent_experiment(self, experiment_id: int) -> dict:
        return self._post(f"/agent/experiments/{experiment_id}/stop")

    def get_agent_experiment_status(self, experiment_id: int) -> dict:
        return self._get(f"/agent/experiments/{experiment_id}/status")

    def get_agent_experiment_results(self, experiment_id: int) -> dict:
        return self._get(f"/agent/experiments/{experiment_id}/results")

    def generate_agent_experiment_report(self, experiment_id: int) -> dict:
        return self._post(f"/agent/experiments/{experiment_id}/report/generate")

    def get_agent_experiment_report(self, experiment_id: int) -> dict:
        return self._get(f"/agent/experiments/{experiment_id}/report")

    def delete_agent_experiment(self, experiment_id: int) -> dict:
        return self._delete(f"/agent/experiments/{experiment_id}")

    # ── token usage ─────────────────────────────────────────────────

    def get_token_usage_summary(self, days: int = 30) -> dict:
        return self._get(f"/token-usage/summary?days={days}")
