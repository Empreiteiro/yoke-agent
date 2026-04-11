"""``yoke install`` — bootstrap a local Yoke checkout.

Clones the Yoke Agent repo (or refreshes an existing checkout), copies
``backend/.env.example`` to ``backend/.env`` if missing, and records
the path in the CLI config so subsequent ``yoke serve`` commands know
where to invoke ``docker compose``.

The CLI itself does not start any servers — that's ``yoke serve``'s
job. Keeping these two concerns separate means an agent can run
``yoke install`` once during onboarding and then choose to use a remote
backend (via ``YOKE_BASE_URL``) without ever touching docker.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import typer

from .. import config as cfg
from ..utils import console, err_console

DEFAULT_REPO_URL = "https://github.com/Empreiteiro/yoke-agent.git"


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run(
    path: Path = typer.Option(
        Path.home() / ".yoke" / "repo",
        "--path",
        help="Where to clone the Yoke repo.",
    ),
    repo: str = typer.Option(
        DEFAULT_REPO_URL,
        "--repo",
        help="Git URL of the Yoke repo.",
    ),
    branch: str = typer.Option("main", "--branch"),
    update: bool = typer.Option(
        False, "--update", help="Pull latest changes if the repo already exists."
    ),
    skip_env: bool = typer.Option(
        False, "--skip-env", help="Don't copy .env.example to .env."
    ),
):
    """Clone (or update) a local Yoke checkout and record its path in the CLI config."""
    if not _have("git"):
        err_console.print(
            "[red]✗ git is not installed.[/red] Install it and re-run."
        )
        raise typer.Exit(code=2)

    path = path.expanduser().resolve()
    git_dir = path / ".git"

    if git_dir.exists():
        if update:
            console.print(f"[cyan]Updating[/cyan] {path}")
            subprocess.run(
                ["git", "-C", str(path), "fetch", "--quiet", "origin", branch],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(path), "reset", "--quiet", "--hard", f"origin/{branch}"],
                check=True,
            )
        else:
            console.print(
                f"[yellow]✓[/yellow] Existing checkout at {path} (use --update to pull)"
            )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        console.print(f"[cyan]Cloning[/cyan] {repo} → {path}")
        subprocess.run(
            ["git", "clone", "--quiet", "--branch", branch, "--depth", "1", repo, str(path)],
            check=True,
        )

    # Bootstrap backend/.env from the example
    env_path = path / "backend" / ".env"
    env_example = path / "backend" / ".env.example"
    if not skip_env and not env_path.exists() and env_example.exists():
        env_path.write_text(env_example.read_text())
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass
        console.print(f"[green]✓[/green] Created {env_path}")
        console.print(
            "  [yellow]>>>[/yellow] Edit this file to add your provider API keys."
        )

    cfg.set_value("repo_path", str(path))
    console.print(f"[green]✓ Yoke installed at[/green] {path}")
    console.print()
    console.print("Next steps:")
    console.print("  1. Edit [bold]" + str(env_path) + "[/bold] to add API keys")
    console.print("  2. Run [bold]yoke serve[/bold] to start the local stack")
    console.print("  3. Run [bold]yoke doctor[/bold] to verify connectivity")
