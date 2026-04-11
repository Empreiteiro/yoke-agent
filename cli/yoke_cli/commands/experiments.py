"""``yoke experiments`` — RAG grid-search experiments."""

from __future__ import annotations

from typing import Optional

import typer

from ..utils import (
    emit,
    handle_http_errors,
    make_client,
    parse_csv_ints,
    parse_csv_strs,
)

app = typer.Typer(no_args_is_help=True, help="RAG grid-search experiments.")


@app.command("list")
@handle_http_errors
def list_experiments(
    json_output: bool = typer.Option(False, "--json"),
):
    """List all RAG experiments."""
    data = make_client().list_experiments()
    emit(
        data,
        json_output,
        columns=["id", "name", "status", "best_score", "dataset_id"],
        title="RAG Experiments",
    )


@app.command("get")
@handle_http_errors
def get(experiment_id: int = typer.Argument(...)):
    """Show experiment details with combination statuses."""
    emit(make_client().get_experiment(experiment_id), json_output=True)


@app.command("create")
@handle_http_errors
def create(
    dataset_id: int = typer.Option(..., "--dataset-id"),
    name: str = typer.Option("", "--name"),
    vectorstore: str = typer.Option(
        "chromadb", "--vectorstore", help="chromadb / pinecone / qdrant / weaviate / pgvector"
    ),
):
    """Create a new RAG experiment."""
    emit(
        make_client().create_experiment(
            dataset_id=dataset_id, name=name, vectorstore_type=vectorstore
        ),
        json_output=True,
    )


@app.command("configure-grid")
@handle_http_errors
def configure_grid(
    experiment_id: int = typer.Argument(...),
    chunk_sizes: Optional[str] = typer.Option(None, "--chunk-sizes", help="CSV ints"),
    chunk_overlaps: Optional[str] = typer.Option(None, "--chunk-overlaps", help="CSV ints"),
    embedding_models: Optional[str] = typer.Option(
        None, "--embedding-models", help="CSV strings"
    ),
    top_k: Optional[str] = typer.Option(None, "--top-k", help="CSV ints"),
    search_types: Optional[str] = typer.Option(None, "--search-types", help="CSV strings"),
    distance_metrics: Optional[str] = typer.Option(
        None, "--distance-metrics", help="CSV strings"
    ),
    embedding_dimensions: Optional[str] = typer.Option(
        None, "--embedding-dimensions", help="CSV ints"
    ),
):
    """Configure the grid-search axes for an experiment."""
    emit(
        make_client().configure_grid_search(
            experiment_id,
            chunk_sizes=parse_csv_ints(chunk_sizes),
            chunk_overlaps=parse_csv_ints(chunk_overlaps),
            embedding_models=parse_csv_strs(embedding_models),
            top_k_values=parse_csv_ints(top_k),
            search_types=parse_csv_strs(search_types),
            distance_metrics=parse_csv_strs(distance_metrics),
            embedding_dimensions=parse_csv_ints(embedding_dimensions),
        ),
        json_output=True,
    )


@app.command("run")
@handle_http_errors
def run(experiment_id: int = typer.Argument(...)):
    """Start running an experiment."""
    emit(make_client().run_experiment(experiment_id), json_output=True)


@app.command("stop")
@handle_http_errors
def stop(experiment_id: int = typer.Argument(...)):
    """Stop a running experiment."""
    emit(make_client().stop_experiment(experiment_id), json_output=True)


@app.command("resume")
@handle_http_errors
def resume(
    experiment_id: int = typer.Argument(...),
    retry_failed: bool = typer.Option(False, "--retry-failed/--no-retry-failed"),
):
    """Resume a stopped/failed experiment."""
    emit(
        make_client().resume_experiment(experiment_id, retry_failed=retry_failed),
        json_output=True,
    )


@app.command("report")
@handle_http_errors
def report(experiment_id: int = typer.Argument(...)):
    """Fetch the report (best config + summary)."""
    emit(make_client().get_experiment_report(experiment_id), json_output=True)


@app.command("delete")
@handle_http_errors
def delete(
    experiment_id: int = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
    """Delete an experiment."""
    if not yes:
        typer.confirm(f"Delete experiment {experiment_id}?", abort=True)
    emit(make_client().delete_experiment(experiment_id), json_output=True)
