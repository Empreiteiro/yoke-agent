"""Shared helpers for Typer commands: client construction, output formatting,
and error handling."""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

from .client import YokeClient
from .config import resolve_api_key, resolve_base_url

console = Console()
err_console = Console(stderr=True)


def make_client(
    base_url: Optional[str] = None, api_key: Optional[str] = None
) -> YokeClient:
    """Build a YokeClient honouring CLI flag → env var → config-file order."""
    return YokeClient(
        base_url=resolve_base_url(base_url),
        api_key=resolve_api_key(api_key),
    )


def print_json(data: Any) -> None:
    """Print parsed JSON to stdout (compact, agent-friendly)."""
    typer.echo(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def print_table(rows: list[dict], columns: list[str], title: Optional[str] = None) -> None:
    """Render a list of dicts as a Rich table."""
    if not rows:
        console.print(f"[dim]No {title or 'rows'}.[/dim]")
        return
    table = Table(title=title, show_lines=False)
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(row.get(c, "")) for c in columns])
    console.print(table)


def emit(data: Any, json_output: bool, columns: Optional[list[str]] = None, title: Optional[str] = None) -> None:
    """Emit data either as JSON or as a Rich table."""
    if json_output or not columns:
        print_json(data)
        return
    if isinstance(data, list):
        print_table(data, columns=columns, title=title)
    else:
        print_json(data)


def handle_http_errors(func):
    """Decorator that turns httpx errors into clean Typer errors with
    sensible exit codes:

      0 — success
      2 — usage error (Typer raises this on its own)
      4 — backend unreachable / connection refused
      5 — backend returned 4xx/5xx
    """
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except httpx.ConnectError as e:
            err_console.print(
                f"[red]✗ Could not reach the Yoke backend.[/red]\n"
                f"  {e}\n"
                f"  Hint: is the backend running? Try [bold]yoke serve[/bold] "
                f"or set YOKE_BASE_URL."
            )
            raise typer.Exit(code=4)
        except httpx.HTTPStatusError as e:
            body: str = ""
            try:
                body = json.dumps(e.response.json(), indent=2, ensure_ascii=False)
            except Exception:
                body = e.response.text
            err_console.print(
                f"[red]✗ Backend returned {e.response.status_code} {e.response.reason_phrase}[/red]\n{body}"
            )
            raise typer.Exit(code=5)
        except FileNotFoundError as e:
            err_console.print(f"[red]✗ File not found:[/red] {e}")
            raise typer.Exit(code=2)
        except Exception as e:  # noqa: BLE001
            err_console.print(f"[red]✗ Error:[/red] {type(e).__name__}: {e}")
            raise typer.Exit(code=1)

    return wrapper


def parse_csv_ints(value: Optional[str]) -> Optional[list[int]]:
    if not value:
        return None
    return [int(x.strip()) for x in value.split(",") if x.strip()]


def parse_csv_floats(value: Optional[str]) -> Optional[list[float]]:
    if not value:
        return None
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def parse_csv_strs(value: Optional[str]) -> Optional[list[str]]:
    if not value:
        return None
    return [x.strip() for x in value.split(",") if x.strip()]
