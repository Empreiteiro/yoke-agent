"""``yoke config`` — read and write the CLI config file at ~/.yoke/config.json."""

from __future__ import annotations

import typer

from .. import config as cfg
from ..utils import print_json

app = typer.Typer(no_args_is_help=True, help="Read and write the CLI config file.")


@app.command("show")
def show():
    """Print the current config."""
    data = cfg.load()
    data["_path"] = str(cfg.CONFIG_PATH)
    print_json(data)


@app.command("set")
def set_value(
    key: str = typer.Argument(..., help="Config key (e.g. base_url, api_key, repo_path)."),
    value: str = typer.Argument(..., help="Value to set."),
):
    """Set a config value."""
    cfg.set_value(key, value)
    typer.echo(f"✓ {key} = {value}")
    typer.echo(f"  ({cfg.CONFIG_PATH})")


@app.command("get")
def get(key: str = typer.Argument(...)):
    """Get a config value."""
    value = cfg.get(key)
    if value is None:
        typer.echo("")
        raise typer.Exit(code=1)
    typer.echo(value)


@app.command("path")
def path():
    """Print the config file path."""
    typer.echo(str(cfg.CONFIG_PATH))
