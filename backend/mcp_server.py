"""MCP Server for RAG Optimization Pipeline.

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
    "RAG Optimization Pipeline",
    description="Control the RAG optimization pipeline: upload documents, generate datasets, configure and run experiments, view results.",
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
