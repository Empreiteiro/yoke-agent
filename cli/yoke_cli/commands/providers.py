"""``yoke providers`` — manage LLM / embedding providers."""

from __future__ import annotations

from typing import Optional

import typer

from ..utils import emit, handle_http_errors, make_client, parse_csv_strs

app = typer.Typer(no_args_is_help=True, help="Manage LLM / embedding providers.")


@app.command("list")
@handle_http_errors
def list_providers(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON."),
):
    """List configured providers."""
    data = make_client().list_providers()
    emit(
        data,
        json_output,
        columns=["id", "name", "provider_type", "is_active", "default_llm_model"],
        title="Providers",
    )


@app.command("get")
@handle_http_errors
def get_provider(
    provider_id: int = typer.Argument(..., help="Provider ID."),
    json_output: bool = typer.Option(True, "--json/--no-json"),
):
    """Show a single provider."""
    data = make_client().get_provider(provider_id)
    emit(data, json_output)


@app.command("catalog")
@handle_http_errors
def catalog(json_output: bool = typer.Option(True, "--json/--no-json")):
    """Show the catalog of supported provider types."""
    data = make_client().get_provider_catalog()
    emit(data, json_output)


@app.command("models")
@handle_http_errors
def models(json_output: bool = typer.Option(True, "--json/--no-json")):
    """List all available models from active providers."""
    data = make_client().get_available_models()
    emit(data, json_output)


@app.command("create")
@handle_http_errors
def create(
    name: str = typer.Option(..., "--name", help="Display name."),
    provider_type: str = typer.Option(
        ..., "--type", help="Provider type (openai, anthropic, google, ...)."
    ),
    api_key: str = typer.Option("", "--api-key", help="API key (if applicable)."),
    base_url: str = typer.Option("", "--base-url", help="Base URL for self-hosted."),
    llm_models: Optional[str] = typer.Option(
        None, "--llm-models", help="Comma-separated LLM model names."
    ),
    embedding_models: Optional[str] = typer.Option(
        None, "--embedding-models", help="Comma-separated embedding model names."
    ),
    default_llm: str = typer.Option("", "--default-llm"),
    default_embedding: str = typer.Option("", "--default-embedding"),
    supports_llm: bool = typer.Option(True, "--llm/--no-llm"),
    supports_embedding: bool = typer.Option(False, "--embedding/--no-embedding"),
    flex_tier: bool = typer.Option(False, "--flex/--no-flex", help="Opt into flex tier."),
):
    """Create a new provider."""
    extra: dict = {}
    if flex_tier:
        extra["flex_tier"] = True
    data = make_client().create_provider(
        name=name,
        provider_type=provider_type,
        api_key=api_key,
        base_url=base_url,
        llm_models=parse_csv_strs(llm_models),
        embedding_models=parse_csv_strs(embedding_models),
        default_llm_model=default_llm,
        default_embedding_model=default_embedding,
        supports_llm=supports_llm,
        supports_embedding=supports_embedding,
        extra_config=extra or None,
    )
    emit(data, json_output=True)


@app.command("update")
@handle_http_errors
def update(
    provider_id: int = typer.Argument(...),
    name: str = typer.Option("", "--name"),
    api_key: str = typer.Option("", "--api-key"),
    base_url: str = typer.Option("", "--base-url"),
    llm_models: Optional[str] = typer.Option(None, "--llm-models"),
    embedding_models: Optional[str] = typer.Option(None, "--embedding-models"),
    default_llm: str = typer.Option("", "--default-llm"),
    default_embedding: str = typer.Option("", "--default-embedding"),
    activate: Optional[bool] = typer.Option(
        None, "--activate/--deactivate", help="Toggle provider on/off."
    ),
    flex_tier: Optional[bool] = typer.Option(
        None, "--flex/--no-flex", help="Toggle flex tier."
    ),
):
    """Update an existing provider."""
    extra = None
    if flex_tier is not None:
        extra = {"flex_tier": flex_tier}
    data = make_client().update_provider(
        provider_id,
        name=name,
        api_key=api_key,
        base_url=base_url,
        llm_models=parse_csv_strs(llm_models),
        embedding_models=parse_csv_strs(embedding_models),
        default_llm_model=default_llm,
        default_embedding_model=default_embedding,
        is_active=activate,
        extra_config=extra,
    )
    emit(data, json_output=True)


@app.command("delete")
@handle_http_errors
def delete(
    provider_id: int = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
):
    """Delete a provider."""
    if not yes:
        typer.confirm(f"Delete provider {provider_id}?", abort=True)
    data = make_client().delete_provider(provider_id)
    emit(data, json_output=True)


@app.command("test")
@handle_http_errors
def test(provider_id: int = typer.Argument(...)):
    """Run a connectivity test against a provider."""
    data = make_client().test_provider(provider_id)
    emit(data, json_output=True)
