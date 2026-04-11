"""Yoke CLI entry point.

Run ``yoke --help`` for the full command tree, or visit individual
sub-apps:

  yoke providers   --  manage LLM/embedding providers
  yoke experiments --  RAG grid-search experiments
  yoke agents      --  agent workbench experiments
  yoke datasets    --  evaluation datasets
  yoke collections --  saved vectorstore collections
  yoke install     --  bootstrap a local Yoke checkout (clone + .env)
  yoke serve       --  start / stop the local stack via docker compose
  yoke doctor      --  verify CLI <-> backend connectivity
"""

from __future__ import annotations

import typer

from . import __version__
from .commands import (
    agents,
    collections,
    config_cmd,
    datasets,
    doctor,
    experiments,
    install,
    providers,
    serve,
)

app = typer.Typer(
    name="yoke",
    help="Yoke Agent CLI — control the AI Quality Studio from your terminal.",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"yoke {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show the CLI version and exit.",
    ),
) -> None:
    """Yoke Agent CLI."""


# ── sub-apps ────────────────────────────────────────────────────────
app.add_typer(providers.app, name="providers", help="Manage LLM / embedding providers.")
app.add_typer(experiments.app, name="experiments", help="RAG grid-search experiments.")
app.add_typer(agents.app, name="agents", help="Agent workbench experiments.")
app.add_typer(datasets.app, name="datasets", help="Evaluation datasets.")
app.add_typer(collections.app, name="collections", help="Saved vectorstore collections.")
app.add_typer(config_cmd.app, name="config", help="Read and write the CLI config file.")

# ── single-shot commands ────────────────────────────────────────────
app.command(name="install", help="Bootstrap a local Yoke checkout (clone + .env).")(
    install.run
)
app.command(name="serve", help="Start the local Yoke stack via docker compose.")(
    serve.up
)
app.command(name="stop", help="Stop the local Yoke stack.")(serve.down)
app.command(name="logs", help="Tail logs from the local stack.")(serve.logs)
app.command(name="doctor", help="Verify CLI <-> backend connectivity.")(doctor.run)


if __name__ == "__main__":
    app()
