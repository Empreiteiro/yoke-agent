"""``yoke collections`` — saved vectorstore collections."""

from __future__ import annotations

import typer

from ..utils import emit, handle_http_errors, make_client

app = typer.Typer(no_args_is_help=True, help="Saved vectorstore collections.")


@app.command("list")
@handle_http_errors
def list_collections(json_output: bool = typer.Option(False, "--json")):
    """List saved collections."""
    data = make_client().list_collections()
    emit(data, json_output, columns=["id", "name", "created_at"], title="Collections")


@app.command("query")
@handle_http_errors
def query(
    collection_id: int = typer.Argument(...),
    question: str = typer.Option(..., "--question", "-q"),
    top_k: int = typer.Option(0, "--top-k"),
):
    """Query a saved collection."""
    emit(
        make_client().query_collection(collection_id, question, top_k=top_k),
        json_output=True,
    )


@app.command("delete")
@handle_http_errors
def delete(
    collection_id: int = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
    """Delete a saved collection."""
    if not yes:
        typer.confirm(f"Delete collection {collection_id}?", abort=True)
    emit(make_client().delete_collection(collection_id), json_output=True)
