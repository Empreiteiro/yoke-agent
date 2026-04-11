"""``yoke serve`` / ``yoke stop`` / ``yoke logs`` — manage the local stack
via docker compose, using the repo path recorded by ``yoke install``."""

from __future__ import annotations

import shutil
import subprocess

import typer

from .. import config as cfg
from ..utils import console, err_console


def _docker_compose_cmd() -> list[str]:
    """Prefer ``docker compose`` (v2 plugin), fall back to ``docker-compose``."""
    if shutil.which("docker"):
        # Quick check: does `docker compose version` work?
        try:
            subprocess.run(
                ["docker", "compose", "version"],
                check=True,
                capture_output=True,
                timeout=5,
            )
            return ["docker", "compose"]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    err_console.print(
        "[red]✗ Neither `docker compose` nor `docker-compose` is available.[/red]\n"
        "  Install Docker Desktop or the compose plugin first."
    )
    raise typer.Exit(code=2)


def _resolve_repo() -> str:
    repo = cfg.resolve_repo_path()
    if not repo or not (repo / "docker-compose.yml").exists():
        err_console.print(
            "[red]✗ No local Yoke checkout found.[/red]\n"
            "  Run [bold]yoke install[/bold] first, or pass --repo manually."
        )
        raise typer.Exit(code=2)
    return str(repo)


def up(
    detach: bool = typer.Option(True, "--detach/--foreground", "-d"),
    build: bool = typer.Option(False, "--build", help="Rebuild images before starting."),
):
    """Start the local Yoke stack via docker compose."""
    repo = _resolve_repo()
    cmd = _docker_compose_cmd() + ["up"]
    if build:
        cmd.append("--build")
    if detach:
        cmd.append("-d")
    console.print(f"[cyan]$[/cyan] {' '.join(cmd)}  ([dim]cwd: {repo}[/dim])")
    result = subprocess.run(cmd, cwd=repo)
    if result.returncode == 0 and detach:
        console.print()
        console.print("[green]✓ Yoke is running:[/green]")
        console.print("  Backend  → http://localhost:4040")
        console.print("  Frontend → http://localhost:4000")
        console.print("  API base → http://localhost:4040/api")
    raise typer.Exit(code=result.returncode)


def down():
    """Stop the local Yoke stack."""
    repo = _resolve_repo()
    cmd = _docker_compose_cmd() + ["down"]
    console.print(f"[cyan]$[/cyan] {' '.join(cmd)}  ([dim]cwd: {repo}[/dim])")
    raise typer.Exit(code=subprocess.run(cmd, cwd=repo).returncode)


def logs(
    follow: bool = typer.Option(True, "--follow/--no-follow", "-f"),
    service: str = typer.Option("", "--service", help="Show logs for one service only."),
):
    """Tail logs from the local stack."""
    repo = _resolve_repo()
    cmd = _docker_compose_cmd() + ["logs"]
    if follow:
        cmd.append("-f")
    if service:
        cmd.append(service)
    raise typer.Exit(code=subprocess.run(cmd, cwd=repo).returncode)
