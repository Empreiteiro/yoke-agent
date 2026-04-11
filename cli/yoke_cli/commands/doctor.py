"""``yoke doctor`` — verify CLI <-> backend connectivity and config."""

from __future__ import annotations

import shutil

import httpx
import typer

from .. import config as cfg
from ..client import YokeClient
from ..utils import console, err_console


def run():
    """Run a series of health checks against the local environment."""
    ok = True

    # 1. Config file
    console.print(f"[bold]Config[/bold]: {cfg.CONFIG_PATH}")
    if cfg.CONFIG_PATH.exists():
        console.print("  [green]✓[/green] config file present")
    else:
        console.print("  [yellow]–[/yellow] no config file (using defaults / env vars)")

    # 2. Resolved settings
    base_url = cfg.resolve_base_url()
    api_key = cfg.resolve_api_key()
    console.print(f"  base_url = {base_url}")
    console.print(f"  api_key  = {'set' if api_key else '[dim](not set)[/dim]'}")
    repo = cfg.resolve_repo_path()
    if repo:
        console.print(f"  repo_path = {repo}")
    else:
        console.print("  repo_path = [dim](not set — `yoke install` to bootstrap)[/dim]")

    # 3. Docker availability (only relevant if user wants to self-host)
    if shutil.which("docker"):
        console.print("[bold]Docker[/bold]: [green]✓ available[/green]")
    else:
        console.print("[bold]Docker[/bold]: [yellow]not installed[/yellow] (only needed for `yoke serve`)")

    # 4. Backend connectivity
    console.print(f"[bold]Backend[/bold]: {base_url}")
    client = YokeClient(base_url=base_url, api_key=api_key)
    try:
        info = client.health()
        if info.get("ok"):
            console.print(
                f"  [green]✓ reachable[/green] (HTTP {info['status_code']})"
            )
        else:
            console.print(
                f"  [yellow]reachable but returned {info['status_code']}[/yellow]"
            )
            ok = False
    except httpx.ConnectError as e:
        err_console.print(f"  [red]✗ connection refused:[/red] {e}")
        err_console.print("    Hint: run [bold]yoke serve[/bold] to start the local stack.")
        ok = False
    except Exception as e:  # noqa: BLE001
        err_console.print(f"  [red]✗ error:[/red] {type(e).__name__}: {e}")
        ok = False

    # 5. List providers as a real round-trip
    if ok:
        try:
            providers = client.list_providers()
            console.print(
                f"[bold]Providers[/bold]: [green]{len(providers)} configured[/green]"
            )
            for p in providers[:5]:
                console.print(f"  • {p.get('name')} ({p.get('provider_type')})")
        except Exception as e:  # noqa: BLE001
            err_console.print(f"  [red]✗ could not list providers:[/red] {e}")
            ok = False

    if not ok:
        raise typer.Exit(code=1)
    console.print()
    console.print("[green]All checks passed.[/green]")
