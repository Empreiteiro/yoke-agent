"""MCP Server for Yoke Agent — AI Quality Studio.

Exposes all platform functionality as MCP tools for AI agent control.
Connects to the FastAPI backend via HTTP through the shared
``YokeClient`` (see ``backend/yoke_client.py``), so the same code path
is used by ``yoke`` CLI commands and by MCP tool calls.

Usage:
    fastmcp run mcp_server.py
    # or via stdio for Claude Code integration

Environment variables:
    YOKE_API_KEY  - API key for the backend (alias: RAG_API_KEY)
    YOKE_BASE_URL - Backend base URL (default: http://localhost:4040/api)
                    (alias: RAG_BASE_URL)
"""

import json
import os

from fastmcp import FastMCP

from yoke_client import YokeClient

mcp = FastMCP(
    "Yoke Agent",
    instructions="AI Quality Studio: optimize RAG pipelines and evaluate AI agents through grid search, simulation testing, and metrics.",
)

# One shared client instance — picks up YOKE_BASE_URL / YOKE_API_KEY
# (with RAG_* legacy fallbacks) from the environment.
_yoke = YokeClient()

# Load disabled tools from config
_config_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "mcp_config.json"
)
_disabled_tools: set[str] = set()
if os.path.exists(_config_path):
    try:
        with open(_config_path) as f:
            _disabled_tools = set(json.load(f).get("disabled_tools", []))
    except Exception:
        pass


def _register(func):
    """Register as MCP tool only if not disabled."""
    if func.__name__ not in _disabled_tools:
        return mcp.tool()(func)
    return func


# ─── Documents ───────────────────────────────────────────


@_register
def list_documents() -> list[dict]:
    """List all uploaded documents."""
    return _yoke.list_documents()


@_register
def upload_document(filepath: str) -> dict:
    """Upload a document file (PDF, TXT, DOCX, MD) to the pipeline.

    Args:
        filepath: Absolute path to the file to upload.
    """
    return _yoke.upload_document(filepath)


# ─── Datasets ────────────────────────────────────────────


@_register
def list_datasets() -> list[dict]:
    """List all evaluation datasets."""
    return _yoke.list_datasets()


@_register
def get_dataset(dataset_id: int) -> dict:
    """Get a dataset by ID with all Q&A items.

    Args:
        dataset_id: The dataset ID.
    """
    return _yoke.get_dataset(dataset_id)


@_register
def create_dataset(
    document_ids: list[int], name: str = "", description: str = ""
) -> dict:
    """Create a new evaluation dataset from uploaded documents.

    Args:
        document_ids: List of document IDs to include.
        name: Optional name for the dataset.
        description: Optional description.
    """
    return _yoke.create_dataset(document_ids, name=name, description=description)


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
    return _yoke.generate_dataset(
        dataset_id,
        reading_mode=reading_mode,
        max_pages=max_pages,
        num_questions=num_questions,
    )


@_register
def approve_dataset(dataset_id: int) -> dict:
    """Approve a dataset for use in experiments.

    Args:
        dataset_id: The dataset ID to approve.
    """
    return _yoke.approve_dataset(dataset_id)


# ─── Experiments ─────────────────────────────────────────


@_register
def list_experiments() -> list[dict]:
    """List all experiments with their status and scores."""
    return _yoke.list_experiments()


@_register
def create_experiment(
    dataset_id: int, name: str = "", vectorstore_type: str = "chromadb"
) -> dict:
    """Create a new experiment.

    Args:
        dataset_id: Dataset ID to evaluate against.
        name: Optional experiment name.
        vectorstore_type: Vector store backend (chromadb, pinecone, qdrant, weaviate, pgvector).
    """
    return _yoke.create_experiment(
        dataset_id, name=name, vectorstore_type=vectorstore_type
    )


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
    return _yoke.configure_grid_search(
        experiment_id,
        chunk_sizes=chunk_sizes,
        chunk_overlaps=chunk_overlaps,
        embedding_models=embedding_models,
        top_k_values=top_k_values,
        search_types=search_types,
        distance_metrics=distance_metrics,
        embedding_dimensions=embedding_dimensions,
    )


@_register
def run_experiment(experiment_id: int) -> dict:
    """Start running an experiment (executes all combinations).

    Args:
        experiment_id: The experiment ID to run.
    """
    return _yoke.run_experiment(experiment_id)


@_register
def stop_experiment(experiment_id: int) -> dict:
    """Stop a running experiment.

    Args:
        experiment_id: The experiment ID to stop.
    """
    return _yoke.stop_experiment(experiment_id)


@_register
def resume_experiment(experiment_id: int, retry_failed: bool = False) -> dict:
    """Resume a stopped or failed experiment.

    Args:
        experiment_id: The experiment ID to resume.
        retry_failed: Whether to also retry failed combinations.
    """
    return _yoke.resume_experiment(experiment_id, retry_failed=retry_failed)


@_register
def get_experiment(experiment_id: int) -> dict:
    """Get experiment details including all combination statuses and scores.

    Args:
        experiment_id: The experiment ID.
    """
    return _yoke.get_experiment(experiment_id)


@_register
def get_experiment_report(experiment_id: int) -> dict:
    """Get the full report for an experiment including best configuration and summary.

    Args:
        experiment_id: The experiment ID.
    """
    return _yoke.get_experiment_report(experiment_id)


@_register
def delete_experiment(experiment_id: int) -> dict:
    """Delete an experiment and all its combinations.

    Args:
        experiment_id: The experiment ID to delete.
    """
    return _yoke.delete_experiment(experiment_id)


# ─── Human ratings (issue #118) ──────────────────────────


@_register
def list_combination_ratings(combination_id: int) -> list[dict]:
    """List all human ratings for a specific experiment combination.

    Args:
        combination_id: The experiment combination ID.
    """
    return _yoke.list_combination_ratings(combination_id)


@_register
def rate_combination_question(
    combination_id: int,
    question_index: int,
    rating: str,
    notes: str = "",
    question_text: str = "",
) -> dict:
    """Rate a single Q&A pair from an experiment combination as correct, incorrect, or partial.

    Use this to record human judgement on individual generated answers so it can
    be correlated with automated RAGAS scores. Calling twice for the same
    (combination, question_index) updates the existing rating.

    Args:
        combination_id: The experiment combination ID.
        question_index: Zero-based index of the question inside the combination's detailed_results.
        rating: One of "correct", "incorrect", "partial".
        notes: Optional reviewer notes explaining the judgement.
        question_text: Optional question text snapshot for traceability.
    """
    return _yoke.rate_combination_question(
        combination_id,
        question_index,
        rating,
        notes=notes,
        question_text=question_text,
    )


@_register
def delete_combination_rating(combination_id: int, rating_id: int) -> dict:
    """Delete a human rating.

    Args:
        combination_id: The experiment combination ID.
        rating_id: The rating ID returned by ``rate_combination_question``.
    """
    return _yoke.delete_combination_rating(combination_id, rating_id)


@_register
def get_experiment_correlation(experiment_id: int) -> dict:
    """Pearson/Spearman correlation between human ratings and RAGAS metrics for an experiment.

    Returns per-metric ``pearson`` and ``spearman`` coefficients pooled across
    all combinations of the experiment, plus rating counts.

    Args:
        experiment_id: The experiment ID.
    """
    return _yoke.get_experiment_correlation(experiment_id)


# ─── Collections ─────────────────────────────────────────


@_register
def list_collections() -> list[dict]:
    """List all saved vectorstore collections from winning experiments."""
    return _yoke.list_collections()


@_register
def query_collection(collection_id: int, question: str, top_k: int = 0) -> dict:
    """Query a saved collection — retrieve contexts and generate an answer.

    Args:
        collection_id: The collection ID to query.
        question: The question to ask.
        top_k: Number of documents to retrieve (0 = use collection default).
    """
    return _yoke.query_collection(collection_id, question, top_k=top_k)


@_register
def delete_collection(collection_id: int) -> dict:
    """Delete a saved collection (does not affect experiment history).

    Args:
        collection_id: The collection ID to delete.
    """
    return _yoke.delete_collection(collection_id)


# ─── Providers ───────────────────────────────────────────


@_register
def list_providers() -> list[dict]:
    """List all configured LLM/embedding providers."""
    return _yoke.list_providers()


@_register
def get_available_models() -> dict:
    """Get all available LLM and embedding models from active providers."""
    return _yoke.get_available_models()


@_register
def get_provider_catalog() -> dict:
    """Get the catalog of supported provider types and their known models.

    Useful before creating a provider to learn which provider_type values
    are accepted and which models each one ships with.
    """
    return _yoke.get_provider_catalog()


@_register
def get_provider(provider_id: int) -> dict:
    """Get a single provider by ID.

    Args:
        provider_id: The provider ID.
    """
    return _yoke.get_provider(provider_id)


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
    return _yoke.create_provider(
        name=name,
        provider_type=provider_type,
        api_key=api_key,
        base_url=base_url,
        llm_models=llm_models,
        embedding_models=embedding_models,
        default_llm_model=default_llm_model,
        default_embedding_model=default_embedding_model,
        supports_llm=supports_llm,
        supports_embedding=supports_embedding,
        extra_config=extra_config,
    )


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
    return _yoke.update_provider(
        provider_id,
        name=name,
        api_key=api_key,
        base_url=base_url,
        llm_models=llm_models,
        embedding_models=embedding_models,
        default_llm_model=default_llm_model,
        default_embedding_model=default_embedding_model,
        is_active=is_active,
        extra_config=extra_config,
    )


@_register
def delete_provider(provider_id: int) -> dict:
    """Delete a provider.

    Args:
        provider_id: The provider to delete.
    """
    return _yoke.delete_provider(provider_id)


@_register
def test_provider(provider_id: int) -> dict:
    """Test connectivity for a provider by issuing a minimal LLM and/or
    embedding call. Honors the provider's flex_tier opt-in.

    Args:
        provider_id: The provider to test.
    """
    return _yoke.test_provider(provider_id)


# ─── Agent Workbench: Configs ────────────────────────────


@_register
def list_agent_configs() -> list[dict]:
    """List all agent configurations (system prompts, tools, constraints)."""
    return _yoke.list_agent_configs()


@_register
def get_agent_config(config_id: int) -> dict:
    """Get an agent configuration by ID.

    Args:
        config_id: The agent config ID.
    """
    return _yoke.get_agent_config(config_id)


@_register
def create_agent_config(
    name: str,
    system_prompt: str = "",
    description: str = "",
    tools: list[dict] | None = None,
    constraints: list[str] | None = None,
    agent_type: str = "builtin",
    http_endpoint: str = "",
    http_auth_header: str = "",
    http_timeout_seconds: int = 60,
) -> dict:
    """Create a new agent configuration.

    Args:
        name: Short name for the agent.
        system_prompt: The agent's system prompt (required for builtin, optional for http).
        description: Optional description.
        tools: Optional list of tool definitions: [{"name": "...", "description": "...", "parameters": {...}}].
        constraints: Optional list of plain-text constraints / safety rules.
        agent_type: "builtin" (default, Yoke runs an LLM with the prompt) or "http"
            (Yoke calls an external HTTP endpoint each turn).
        http_endpoint: Required when agent_type="http". POST URL that accepts the
            Yoke chat payload; OpenAI-compatible chat-completion endpoints also work.
        http_auth_header: Optional auth header for the HTTP endpoint — either
            "Bearer <token>" or a full "Header-Name: value" pair.
        http_timeout_seconds: Per-turn timeout for HTTP agents (1-600). Default 60.
    """
    return _yoke.create_agent_config(
        name=name,
        system_prompt=system_prompt,
        description=description,
        tools=tools,
        constraints=constraints,
        agent_type=agent_type,
        http_endpoint=http_endpoint or None,
        http_auth_header=http_auth_header or None,
        http_timeout_seconds=http_timeout_seconds,
    )


@_register
def update_agent_config(
    config_id: int,
    name: str = "",
    description: str = "",
    system_prompt: str = "",
    tools: list[dict] | None = None,
    constraints: list[str] | None = None,
    agent_type: str = "",
    http_endpoint: str = "",
    http_auth_header: str = "",
    http_timeout_seconds: int = 0,
) -> dict:
    """Update an agent configuration. Only non-empty / non-None fields
    are sent.

    Args:
        config_id: The agent config to update.
        agent_type: Optional — "builtin" or "http". Leave empty to keep current.
        http_endpoint: Optional — update the external HTTP endpoint.
        http_auth_header: Optional — update the auth header.
        http_timeout_seconds: Optional — update the per-turn timeout. 0 = keep current.
    """
    return _yoke.update_agent_config(
        config_id,
        name=name,
        description=description,
        system_prompt=system_prompt,
        tools=tools,
        constraints=constraints,
        agent_type=agent_type or None,
        http_endpoint=http_endpoint or None,
        http_auth_header=http_auth_header or None,
        http_timeout_seconds=http_timeout_seconds if http_timeout_seconds > 0 else None,
    )


@_register
def delete_agent_config(config_id: int) -> dict:
    """Delete an agent configuration and all related variants/scenarios/personas.

    Args:
        config_id: The agent config to delete.
    """
    return _yoke.delete_agent_config(config_id)


@_register
def test_http_agent_endpoint(
    http_endpoint: str,
    http_auth_header: str = "",
    http_timeout_seconds: int = 30,
    sample_message: str = "Hello, this is a connection test from Yoke Agent.",
) -> dict:
    """Test connectivity to an external HTTP agent endpoint (issue #169).

    Fires a single POST and reports status, latency, detected response
    format ("native", "openai", or "text"), and how many tool_calls were
    detected. Use this before creating an HTTP agent config so you can
    validate the endpoint and auth first.

    Args:
        http_endpoint: POST URL to hit (must start with http:// or https://).
        http_auth_header: Optional auth header — "Bearer <token>" or
            "Header-Name: value".
        http_timeout_seconds: Timeout in seconds (1-300). Default 30.
        sample_message: Test user message sent to the endpoint.
    """
    return _yoke.test_http_agent_endpoint(
        http_endpoint=http_endpoint,
        http_auth_header=http_auth_header or None,
        http_timeout_seconds=http_timeout_seconds,
        sample_message=sample_message,
    )


@_register
def test_saved_http_agent(config_id: int) -> dict:
    """Test the stored HTTP endpoint of an already-saved agent config.

    Args:
        config_id: The agent config ID (must have agent_type="http").
    """
    return _yoke.test_saved_http_agent(config_id)


# ─── Agent Workbench: Prompt Variants ────────────────────


@_register
def list_prompt_variants(config_id: int) -> list[dict]:
    """List all prompt variants for an agent config.

    Args:
        config_id: The agent config ID.
    """
    return _yoke.list_prompt_variants(config_id)


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
    return _yoke.generate_prompt_variants(config_id, count=count, focus=focus)


# ─── Agent Workbench: Scenarios ──────────────────────────


@_register
def list_scenarios(config_id: int) -> list[dict]:
    """List all test scenarios for an agent config.

    Args:
        config_id: The agent config ID.
    """
    return _yoke.list_scenarios(config_id)


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
    return _yoke.generate_scenarios(
        config_id, scenario_type=scenario_type, count=count
    )


# ─── Agent Workbench: Personas ───────────────────────────


@_register
def list_personas(config_id: int) -> list[dict]:
    """List all synthetic personas for an agent config.

    Args:
        config_id: The agent config ID.
    """
    return _yoke.list_personas(config_id)


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
    return _yoke.generate_personas(
        config_id,
        audience_description=audience_description,
        count=count,
        interaction_count=interaction_count,
    )


# ─── Agent Workbench: Experiments ────────────────────────


@_register
def list_agent_experiments() -> list[dict]:
    """List all agent experiments with their status and grid configuration."""
    return _yoke.list_agent_experiments()


@_register
def get_agent_experiment(experiment_id: int) -> dict:
    """Get an agent experiment by ID.

    Args:
        experiment_id: The agent experiment ID.
    """
    return _yoke.get_agent_experiment(experiment_id)


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
    return _yoke.create_agent_experiment(
        name=name,
        agent_config_id=agent_config_id,
        prompt_variant_ids=prompt_variant_ids,
        llm_models=llm_models,
        temperatures=temperatures,
        persona_group_names=persona_group_names,
        scenario_types=scenario_types,
        max_turns=max_turns,
        description=description,
    )


@_register
def run_agent_experiment(experiment_id: int) -> dict:
    """Start running an agent experiment (executes all combinations).

    Args:
        experiment_id: The agent experiment ID.
    """
    return _yoke.run_agent_experiment(experiment_id)


@_register
def stop_agent_experiment(experiment_id: int) -> dict:
    """Stop a running agent experiment.

    Args:
        experiment_id: The agent experiment ID.
    """
    return _yoke.stop_agent_experiment(experiment_id)


@_register
def get_agent_experiment_status(experiment_id: int) -> dict:
    """Get current status (combinations done/total/failed) for an agent experiment.

    Args:
        experiment_id: The agent experiment ID.
    """
    return _yoke.get_agent_experiment_status(experiment_id)


@_register
def get_agent_experiment_results(experiment_id: int) -> dict:
    """Get aggregated results for an agent experiment, ranked by score.

    Args:
        experiment_id: The agent experiment ID.
    """
    return _yoke.get_agent_experiment_results(experiment_id)


@_register
def generate_agent_experiment_report(experiment_id: int) -> dict:
    """Generate an LLM-powered improvement report for an agent experiment.

    Args:
        experiment_id: The agent experiment ID.
    """
    return _yoke.generate_agent_experiment_report(experiment_id)


@_register
def get_agent_experiment_report(experiment_id: int) -> dict:
    """Fetch a previously-generated improvement report for an agent experiment.

    Args:
        experiment_id: The agent experiment ID.
    """
    return _yoke.get_agent_experiment_report(experiment_id)


@_register
def delete_agent_experiment(experiment_id: int) -> dict:
    """Delete an agent experiment and all its combinations/transcripts.

    Args:
        experiment_id: The agent experiment ID.
    """
    return _yoke.delete_agent_experiment(experiment_id)


# ─── Token Usage ─────────────────────────────────────────


@_register
def get_token_usage_summary(days: int = 30) -> dict:
    """Get token usage summary with breakdowns by day, model, and operation.

    Args:
        days: Number of days to look back (default 30).
    """
    return _yoke.get_token_usage_summary(days=days)


if __name__ == "__main__":
    mcp.run()
