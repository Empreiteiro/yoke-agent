"""MCP Server for Yoke Agent — AI Quality Studio.

Exposes all platform functionality as MCP tools for AI agent control.
Connects to the FastAPI backend via HTTP.

Usage:
    fastmcp run mcp_server.py
    # or via stdio for Claude Code integration

Environment variables:
    RAG_API_KEY  - API key for authenticating with the backend
    RAG_BASE_URL - Backend base URL (default: http://localhost:4040/api)
"""

import os
import json
import httpx
from fastmcp import FastMCP

mcp = FastMCP(
    "Yoke Agent",
    instructions="AI Quality Studio: optimize RAG pipelines and evaluate AI agents through grid search, simulation testing, and metrics.",
)

API_KEY = os.environ.get("RAG_API_KEY", "")
BASE_URL = os.environ.get("RAG_BASE_URL", "http://localhost:4040/api")

# Load disabled tools from config
_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "mcp_config.json")
_disabled_tools: set[str] = set()
if os.path.exists(_config_path):
    try:
        with open(_config_path) as f:
            _disabled_tools = set(json.load(f).get("disabled_tools", []))
    except Exception:
        pass


def _client() -> httpx.Client:
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    return httpx.Client(base_url=BASE_URL, timeout=120, headers=headers)


def _register(func):
    """Register as MCP tool only if not disabled."""
    if func.__name__ not in _disabled_tools:
        return mcp.tool()(func)
    return func


# ─── Documents ───────────────────────────────────────────

@_register
def list_documents() -> list[dict]:
    """List all uploaded documents."""
    with _client() as c:
        return c.get("/documents/").json()


@_register
def upload_document(filepath: str) -> dict:
    """Upload a document file (PDF, TXT, DOCX, MD) to the pipeline.

    Args:
        filepath: Absolute path to the file to upload.
    """
    import os as _os
    filename = _os.path.basename(filepath)
    with open(filepath, "rb") as f:
        with _client() as c:
            return c.post("/documents/upload", files={"file": (filename, f)}).json()


# ─── Datasets ────────────────────────────────────────────

@_register
def list_datasets() -> list[dict]:
    """List all evaluation datasets."""
    with _client() as c:
        return c.get("/datasets/").json()


@_register
def get_dataset(dataset_id: int) -> dict:
    """Get a dataset by ID with all Q&A items.

    Args:
        dataset_id: The dataset ID.
    """
    with _client() as c:
        return c.get(f"/datasets/{dataset_id}").json()


@_register
def create_dataset(document_ids: list[int], name: str = "", description: str = "") -> dict:
    """Create a new evaluation dataset from uploaded documents.

    Args:
        document_ids: List of document IDs to include.
        name: Optional name for the dataset.
        description: Optional description.
    """
    with _client() as c:
        return c.post("/datasets/", json={
            "name": name or None,
            "description": description or None,
            "document_ids": document_ids,
        }).json()


@_register
def generate_dataset(
    dataset_id: int,
    reading_mode: str = "full",
    max_pages: int = 0,
    num_questions: int = 0,
) -> dict:
    """Generate Q&A pairs for a dataset using LLM.

    Args:
        dataset_id: The dataset ID to generate for.
        reading_mode: "full" for all pages, "partial" for random subset.
        max_pages: When partial, max pages to read. 0 = no limit.
        num_questions: Number of questions. 0 = auto-calculate.
    """
    options = {"reading_mode": reading_mode}
    if max_pages > 0:
        options["max_pages"] = max_pages
    if num_questions > 0:
        options["num_questions"] = num_questions
    with _client() as c:
        return c.post(f"/datasets/{dataset_id}/generate", json=options).json()


@_register
def approve_dataset(dataset_id: int) -> dict:
    """Approve a dataset for use in experiments.

    Args:
        dataset_id: The dataset ID to approve.
    """
    with _client() as c:
        return c.post(f"/datasets/{dataset_id}/approve").json()


# ─── Experiments ─────────────────────────────────────────

@_register
def list_experiments() -> list[dict]:
    """List all experiments with their status and scores."""
    with _client() as c:
        return c.get("/experiments/").json()


@_register
def create_experiment(dataset_id: int, name: str = "", vectorstore_type: str = "chromadb") -> dict:
    """Create a new experiment.

    Args:
        dataset_id: Dataset ID to evaluate against.
        name: Optional experiment name.
        vectorstore_type: Vector store backend (chromadb, pinecone, qdrant, weaviate, pgvector).
    """
    with _client() as c:
        return c.post("/experiments/", json={
            "name": name or None,
            "dataset_id": dataset_id,
            "vectorstore_type": vectorstore_type,
        }).json()


@_register
def configure_grid_search(
    experiment_id: int,
    chunk_sizes: list[int] = [512, 1024],
    chunk_overlaps: list[int] = [10, 20],
    embedding_models: list[str] = ["text-embedding-3-small"],
    top_k_values: list[int] = [3, 5],
    search_types: list[str] = ["vector"],
    distance_metrics: list[str] = ["cosine"],
    embedding_dimensions: list[int] = [],
) -> dict:
    """Configure grid search parameters for an experiment.

    Args:
        experiment_id: The experiment ID.
        chunk_sizes: List of chunk sizes in tokens.
        chunk_overlaps: List of overlap percentages.
        embedding_models: List of embedding model names.
        top_k_values: List of top-K retrieval values.
        search_types: List of search types (vector, hybrid, mmr).
        distance_metrics: List of distance metrics (cosine, l2, ip).
        embedding_dimensions: List of embedding dimensions (empty = model defaults).
    """
    with _client() as c:
        return c.post(f"/experiments/{experiment_id}/configure-grid", json={
            "chunk_sizes": chunk_sizes,
            "chunk_overlaps": chunk_overlaps,
            "embedding_models": embedding_models,
            "top_k_values": top_k_values,
            "search_types": search_types,
            "distance_metrics": distance_metrics,
            "embedding_dimensions": embedding_dimensions,
        }).json()


@_register
def run_experiment(experiment_id: int) -> dict:
    """Start running an experiment (executes all combinations).

    Args:
        experiment_id: The experiment ID to run.
    """
    with _client() as c:
        return c.post(f"/experiments/{experiment_id}/run").json()


@_register
def stop_experiment(experiment_id: int) -> dict:
    """Stop a running experiment.

    Args:
        experiment_id: The experiment ID to stop.
    """
    with _client() as c:
        return c.post(f"/experiments/{experiment_id}/stop").json()


@_register
def resume_experiment(experiment_id: int, retry_failed: bool = False) -> dict:
    """Resume a stopped or failed experiment.

    Args:
        experiment_id: The experiment ID to resume.
        retry_failed: Whether to also retry failed combinations.
    """
    with _client() as c:
        return c.post(f"/experiments/{experiment_id}/resume?retry_failed={retry_failed}").json()


@_register
def get_experiment(experiment_id: int) -> dict:
    """Get experiment details including all combination statuses and scores.

    Args:
        experiment_id: The experiment ID.
    """
    with _client() as c:
        return c.get(f"/experiments/{experiment_id}").json()


@_register
def get_experiment_report(experiment_id: int) -> dict:
    """Get the full report for an experiment including best configuration and summary.

    Args:
        experiment_id: The experiment ID.
    """
    with _client() as c:
        return c.get(f"/experiments/{experiment_id}/report").json()


@_register
def delete_experiment(experiment_id: int) -> dict:
    """Delete an experiment and all its combinations.

    Args:
        experiment_id: The experiment ID to delete.
    """
    with _client() as c:
        return c.delete(f"/experiments/{experiment_id}").json()


# ─── Collections ─────────────────────────────────────────

@_register
def list_collections() -> list[dict]:
    """List all saved vectorstore collections from winning experiments."""
    with _client() as c:
        return c.get("/collections/").json()


@_register
def query_collection(collection_id: int, question: str, top_k: int = 0) -> dict:
    """Query a saved collection — retrieve contexts and generate an answer.

    Args:
        collection_id: The collection ID to query.
        question: The question to ask.
        top_k: Number of documents to retrieve (0 = use collection default).
    """
    data = {"question": question}
    if top_k > 0:
        data["top_k"] = top_k
    with _client() as c:
        return c.post(f"/collections/{collection_id}/query", json=data).json()


@_register
def delete_collection(collection_id: int) -> dict:
    """Delete a saved collection (does not affect experiment history).

    Args:
        collection_id: The collection ID to delete.
    """
    with _client() as c:
        return c.delete(f"/collections/{collection_id}").json()


# ─── Providers ───────────────────────────────────────────

@_register
def list_providers() -> list[dict]:
    """List all configured LLM/embedding providers."""
    with _client() as c:
        return c.get("/providers/").json()


@_register
def get_available_models() -> dict:
    """Get all available LLM and embedding models from active providers."""
    with _client() as c:
        return c.get("/providers/models/available").json()


@_register
def get_provider_catalog() -> dict:
    """Get the catalog of supported provider types and their known models.

    Useful before creating a provider to learn which provider_type values
    are accepted and which models each one ships with.
    """
    with _client() as c:
        return c.get("/providers/catalog").json()


@_register
def get_provider(provider_id: int) -> dict:
    """Get a single provider by ID.

    Args:
        provider_id: The provider ID.
    """
    with _client() as c:
        return c.get(f"/providers/{provider_id}").json()


@_register
def create_provider(
    name: str,
    provider_type: str,
    api_key: str = "",
    base_url: str = "",
    llm_models: list[str] | None = None,
    embedding_models: list[str] | None = None,
    default_llm_model: str = "",
    default_embedding_model: str = "",
    supports_llm: bool = True,
    supports_embedding: bool = False,
    extra_config: dict | None = None,
) -> dict:
    """Create a new LLM/embedding provider.

    Args:
        name: Display name for the provider.
        provider_type: One of the catalog keys (openai, anthropic, google,
            cohere, ollama, azure_openai, huggingface, claude_code, custom).
        api_key: API key for the provider (omit for ollama/claude_code).
        base_url: Base URL for self-hosted/custom providers.
        llm_models: List of LLM model names this provider should expose.
        embedding_models: List of embedding model names.
        default_llm_model: Default LLM model to use when none is specified.
        default_embedding_model: Default embedding model.
        supports_llm: Whether this provider exposes chat/completion models.
        supports_embedding: Whether this provider exposes embedding models.
        extra_config: Provider-specific config. Recognized keys:
            - flex_tier (bool): opt into flex service tier (~50% cheaper,
              best-effort latency). Only effective on flex-eligible models.
            - api_version (str): Azure OpenAI API version.
    """
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
    with _client() as c:
        return c.post("/providers/", json=payload).json()


@_register
def update_provider(
    provider_id: int,
    name: str = "",
    api_key: str = "",
    base_url: str = "",
    llm_models: list[str] | None = None,
    embedding_models: list[str] | None = None,
    default_llm_model: str = "",
    default_embedding_model: str = "",
    is_active: bool | None = None,
    extra_config: dict | None = None,
) -> dict:
    """Update a provider. Only fields that are passed (non-empty / non-None)
    are sent to the backend — everything else is left untouched.

    Args:
        provider_id: The provider to update.
        name: New display name.
        api_key: New API key.
        base_url: New base URL.
        llm_models: Replace the LLM model list.
        embedding_models: Replace the embedding model list.
        default_llm_model: New default LLM model.
        default_embedding_model: New default embedding model.
        is_active: Toggle the provider on/off.
        extra_config: Replace the extra_config dict (e.g. {"flex_tier": true}).
    """
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
    with _client() as c:
        return c.put(f"/providers/{provider_id}", json=payload).json()


@_register
def delete_provider(provider_id: int) -> dict:
    """Delete a provider.

    Args:
        provider_id: The provider to delete.
    """
    with _client() as c:
        return c.delete(f"/providers/{provider_id}").json()


@_register
def test_provider(provider_id: int) -> dict:
    """Test connectivity for a provider by issuing a minimal LLM and/or
    embedding call. Honors the provider's flex_tier opt-in.

    Args:
        provider_id: The provider to test.
    """
    with _client() as c:
        return c.post(f"/providers/{provider_id}/test").json()


# ─── Agent Workbench: Configs ────────────────────────────


@_register
def list_agent_configs() -> list[dict]:
    """List all agent configurations (system prompts, tools, constraints)."""
    with _client() as c:
        return c.get("/agent/configs/").json()


@_register
def get_agent_config(config_id: int) -> dict:
    """Get an agent configuration by ID.

    Args:
        config_id: The agent config ID.
    """
    with _client() as c:
        return c.get(f"/agent/configs/{config_id}").json()


@_register
def create_agent_config(
    name: str,
    system_prompt: str,
    description: str = "",
    tools: list[dict] | None = None,
    constraints: list[str] | None = None,
) -> dict:
    """Create a new agent configuration.

    Args:
        name: Short name for the agent.
        system_prompt: The agent's system prompt.
        description: Optional description.
        tools: Optional list of tool definitions: [{"name": "...", "description": "...", "parameters": {...}}].
        constraints: Optional list of plain-text constraints / safety rules.
    """
    payload = {
        "name": name,
        "system_prompt": system_prompt,
        "description": description or None,
        "tools": tools or [],
        "constraints": constraints or [],
    }
    with _client() as c:
        return c.post("/agent/configs/", json=payload).json()


@_register
def update_agent_config(
    config_id: int,
    name: str = "",
    description: str = "",
    system_prompt: str = "",
    tools: list[dict] | None = None,
    constraints: list[str] | None = None,
) -> dict:
    """Update an agent configuration. Only non-empty / non-None fields
    are sent.

    Args:
        config_id: The agent config to update.
    """
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
    with _client() as c:
        return c.put(f"/agent/configs/{config_id}", json=payload).json()


@_register
def delete_agent_config(config_id: int) -> dict:
    """Delete an agent configuration and all related variants/scenarios/personas.

    Args:
        config_id: The agent config to delete.
    """
    with _client() as c:
        c.delete(f"/agent/configs/{config_id}")
        return {"detail": "deleted"}


# ─── Agent Workbench: Prompt Variants ────────────────────


@_register
def list_prompt_variants(config_id: int) -> list[dict]:
    """List all prompt variants for an agent config.

    Args:
        config_id: The agent config ID.
    """
    with _client() as c:
        return c.get(f"/agent/configs/{config_id}/variants").json()


@_register
def generate_prompt_variants(
    config_id: int, count: int = 3, focus: str = ""
) -> list[dict]:
    """Use an LLM to generate N prompt variations for the agent.

    Args:
        config_id: The agent config to generate variants for.
        count: How many variants to generate.
        focus: Optional steering hint, e.g. "conciseness", "tone", "detail".
    """
    payload = {"count": count, "focus": focus or None}
    with _client() as c:
        return c.post(f"/agent/configs/{config_id}/variants/generate", json=payload).json()


# ─── Agent Workbench: Scenarios ──────────────────────────


@_register
def list_scenarios(config_id: int) -> list[dict]:
    """List all test scenarios for an agent config.

    Args:
        config_id: The agent config ID.
    """
    with _client() as c:
        return c.get(f"/agent/configs/{config_id}/scenarios").json()


@_register
def generate_scenarios(
    config_id: int, scenario_type: str = "response_quality", count: int = 5
) -> list[dict]:
    """Use an LLM to generate test scenarios for the agent.

    Args:
        config_id: The agent config ID.
        scenario_type: One of: tool_use, decision_path, response_quality, guardrail.
        count: How many scenarios to generate.
    """
    payload = {"scenario_type": scenario_type, "count": count}
    with _client() as c:
        return c.post(f"/agent/configs/{config_id}/scenarios/generate", json=payload).json()


# ─── Agent Workbench: Personas ───────────────────────────


@_register
def list_personas(config_id: int) -> list[dict]:
    """List all synthetic personas for an agent config.

    Args:
        config_id: The agent config ID.
    """
    with _client() as c:
        return c.get(f"/agent/configs/{config_id}/personas").json()


@_register
def generate_personas(
    config_id: int,
    audience_description: str,
    count: int = 5,
    interaction_count: int = 10,
) -> list[dict]:
    """Use an LLM to generate diverse synthetic personas.

    Args:
        config_id: The agent config ID.
        audience_description: Free-text description of the target audience.
        count: How many personas to generate.
        interaction_count: How many simulated interactions each persona will run.
    """
    payload = {
        "audience_description": audience_description,
        "count": count,
        "interaction_count": interaction_count,
    }
    with _client() as c:
        return c.post(f"/agent/configs/{config_id}/personas/generate", json=payload).json()


# ─── Agent Workbench: Experiments ────────────────────────


@_register
def list_agent_experiments() -> list[dict]:
    """List all agent experiments with their status and grid configuration."""
    with _client() as c:
        return c.get("/agent/experiments").json()


@_register
def get_agent_experiment(experiment_id: int) -> dict:
    """Get an agent experiment by ID.

    Args:
        experiment_id: The agent experiment ID.
    """
    with _client() as c:
        return c.get(f"/agent/experiments/{experiment_id}").json()


@_register
def create_agent_experiment(
    name: str,
    agent_config_id: int,
    prompt_variant_ids: list[int],
    llm_models: list[str],
    temperatures: list[float] | None = None,
    persona_group_names: list[str] | None = None,
    scenario_types: list[str] | None = None,
    max_turns: list[int] | None = None,
    description: str = "",
) -> dict:
    """Create an agent experiment with a grid-search configuration.

    Args:
        name: Experiment name.
        agent_config_id: The agent config under test.
        prompt_variant_ids: Prompt variants to test (must belong to the agent config).
        llm_models: LLM model names to test (e.g. ["gpt-4o-mini", "gemini-2.5-flash"]).
        temperatures: Temperature values to test. Defaults to [0.0].
        persona_group_names: Persona groups to include (empty = all).
        scenario_types: Scenario types to include (empty = all).
        max_turns: Max conversation turns per scenario. Defaults to [1].
        description: Optional description.
    """
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
    with _client() as c:
        return c.post("/agent/experiments", json=payload).json()


@_register
def run_agent_experiment(experiment_id: int) -> dict:
    """Start running an agent experiment (executes all combinations).

    Args:
        experiment_id: The agent experiment ID.
    """
    with _client() as c:
        return c.post(f"/agent/experiments/{experiment_id}/run").json()


@_register
def stop_agent_experiment(experiment_id: int) -> dict:
    """Stop a running agent experiment.

    Args:
        experiment_id: The agent experiment ID.
    """
    with _client() as c:
        return c.post(f"/agent/experiments/{experiment_id}/stop").json()


@_register
def get_agent_experiment_status(experiment_id: int) -> dict:
    """Get current status (combinations done/total/failed) for an agent experiment.

    Args:
        experiment_id: The agent experiment ID.
    """
    with _client() as c:
        return c.get(f"/agent/experiments/{experiment_id}/status").json()


@_register
def get_agent_experiment_results(experiment_id: int) -> dict:
    """Get aggregated results for an agent experiment, ranked by score.

    Args:
        experiment_id: The agent experiment ID.
    """
    with _client() as c:
        return c.get(f"/agent/experiments/{experiment_id}/results").json()


@_register
def generate_agent_experiment_report(experiment_id: int) -> dict:
    """Generate an LLM-powered improvement report for an agent experiment.

    Args:
        experiment_id: The agent experiment ID.
    """
    with _client() as c:
        return c.post(f"/agent/experiments/{experiment_id}/report/generate").json()


@_register
def get_agent_experiment_report(experiment_id: int) -> dict:
    """Fetch a previously-generated improvement report for an agent experiment.

    Args:
        experiment_id: The agent experiment ID.
    """
    with _client() as c:
        return c.get(f"/agent/experiments/{experiment_id}/report").json()


@_register
def delete_agent_experiment(experiment_id: int) -> dict:
    """Delete an agent experiment and all its combinations/transcripts.

    Args:
        experiment_id: The agent experiment ID.
    """
    with _client() as c:
        c.delete(f"/agent/experiments/{experiment_id}")
        return {"detail": "deleted"}


# ─── Token Usage ─────────────────────────────────────────

@_register
def get_token_usage_summary(days: int = 30) -> dict:
    """Get token usage summary with breakdowns by day, model, and operation.

    Args:
        days: Number of days to look back (default 30).
    """
    with _client() as c:
        return c.get(f"/token-usage/summary?days={days}").json()


if __name__ == "__main__":
    mcp.run()
