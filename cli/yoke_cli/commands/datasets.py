"""``yoke datasets`` — evaluation datasets."""

from __future__ import annotations

from typing import Optional

import typer

from ..utils import emit, handle_http_errors, make_client, parse_csv_ints

app = typer.Typer(no_args_is_help=True, help="Evaluation datasets.")


@app.command("list")
@handle_http_errors
def list_datasets(json_output: bool = typer.Option(False, "--json")):
    """List datasets."""
    data = make_client().list_datasets()
    emit(data, json_output, columns=["id", "name", "status"], title="Datasets")


@app.command("get")
@handle_http_errors
def get(dataset_id: int = typer.Argument(...)):
    """Show one dataset."""
    emit(make_client().get_dataset(dataset_id), json_output=True)


@app.command("create")
@handle_http_errors
def create(
    document_ids: str = typer.Option(..., "--documents", help="CSV of document IDs."),
    name: str = typer.Option("", "--name"),
    description: str = typer.Option("", "--description"),
):
    """Create a dataset from uploaded documents."""
    emit(
        make_client().create_dataset(
            document_ids=parse_csv_ints(document_ids) or [],
            name=name,
            description=description,
        ),
        json_output=True,
    )


@app.command("generate")
@handle_http_errors
def generate(
    dataset_id: int = typer.Argument(...),
    reading_mode: str = typer.Option("full", "--mode", help="full / partial"),
    max_pages: int = typer.Option(0, "--max-pages"),
    num_questions: int = typer.Option(0, "--num-questions"),
):
    """Generate Q&A pairs for a dataset."""
    emit(
        make_client().generate_dataset(
            dataset_id,
            reading_mode=reading_mode,
            max_pages=max_pages,
            num_questions=num_questions,
        ),
        json_output=True,
    )


@app.command("approve")
@handle_http_errors
def approve(dataset_id: int = typer.Argument(...)):
    """Approve a dataset for use in experiments."""
    emit(make_client().approve_dataset(dataset_id), json_output=True)
