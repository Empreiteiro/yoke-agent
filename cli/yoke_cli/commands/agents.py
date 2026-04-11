"""``yoke agents`` — Agent workbench experiments."""

from __future__ import annotations

from typing import Optional

import typer

from ..utils import (
    emit,
    handle_http_errors,
    make_client,
    parse_csv_floats,
    parse_csv_ints,
    parse_csv_strs,
)

app = typer.Typer(no_args_is_help=True, help="Agent workbench experiments.")


# ── configs ─────────────────────────────────────────────────────────


@app.command("configs")
@handle_http_errors
def list_configs(json_output: bool = typer.Option(False, "--json")):
    """List agent configurations."""
    data = make_client().list_agent_configs()
    emit(data, json_output, columns=["id", "name", "description"], title="Agent Configs")


@app.command("config")
@handle_http_errors
def get_config(config_id: int = typer.Argument(...)):
    """Show one agent configuration."""
    emit(make_client().get_agent_config(config_id), json_output=True)


@app.command("variants")
@handle_http_errors
def list_variants(config_id: int = typer.Argument(...)):
    """List prompt variants for an agent config."""
    emit(make_client().list_prompt_variants(config_id), json_output=True)


@app.command("scenarios")
@handle_http_errors
def list_scenarios(config_id: int = typer.Argument(...)):
    """List test scenarios for an agent config."""
    emit(make_client().list_scenarios(config_id), json_output=True)


@app.command("personas")
@handle_http_errors
def list_personas(config_id: int = typer.Argument(...)):
    """List personas for an agent config."""
    emit(make_client().list_personas(config_id), json_output=True)


# ── External HTTP agents (issue #169) ───────────────────────────────


def _read_template_source(body_template: Optional[str], body_template_file: Optional[str]) -> Optional[str]:
    """Resolve `--body-template` or `--body-template-file` into a string."""
    if body_template_file:
        with open(body_template_file, "r", encoding="utf-8") as f:
            return f.read()
    return body_template


@app.command("create-http")
@handle_http_errors
def create_http_agent(
    name: str = typer.Option(..., "--name", help="Agent name"),
    endpoint: str = typer.Option(..., "--endpoint", help="HTTP POST URL (https://...)"),
    description: str = typer.Option("", "--description"),
    auth_header: str = typer.Option("", "--auth-header", help="'Bearer <token>' or 'Header-Name: value'"),
    timeout: int = typer.Option(60, "--timeout", help="Per-turn timeout in seconds (1-600)"),
    body_template: Optional[str] = typer.Option(
        None, "--body-template", help="JSON template with {{var}} placeholders (use --body-template-file for multi-line)"
    ),
    body_template_file: Optional[str] = typer.Option(
        None, "--body-template-file", help="Path to a JSON template file (alternative to --body-template)"
    ),
    response_path: Optional[str] = typer.Option(
        None, "--response-path", help="Dotted JSON path to the content field, e.g. 'choices[0].message.content'"
    ),
    tool_calls_path: Optional[str] = typer.Option(
        None, "--tool-calls-path", help="Dotted JSON path to the tool_calls array in the response"
    ),
):
    """Register an external HTTP agent in Yoke (no prompt/tools required).

    The endpoint will be POSTed once per turn during simulations. Pass
    --body-template (or --body-template-file) to customize the request
    shape with {{var}} placeholders; leave it empty to send the Yoke
    native shape. Set --response-path for non-standard response layouts.
    """
    template = _read_template_source(body_template, body_template_file)
    emit(
        make_client().create_agent_config(
            name=name,
            description=description,
            system_prompt="",
            agent_type="http",
            http_endpoint=endpoint,
            http_auth_header=auth_header or None,
            http_timeout_seconds=timeout,
            http_body_template=template,
            http_response_path=response_path,
            http_tool_calls_path=tool_calls_path,
        ),
        json_output=True,
    )


@app.command("test-http")
@handle_http_errors
def test_http_agent(
    endpoint: Optional[str] = typer.Option(None, "--endpoint", help="Test an arbitrary URL"),
    config_id: Optional[int] = typer.Option(None, "--config-id", help="Test a saved HTTP agent"),
    auth_header: str = typer.Option("", "--auth-header"),
    timeout: int = typer.Option(30, "--timeout"),
    message: str = typer.Option(
        "Hello, this is a connection test from Yoke Agent.", "--message"
    ),
    body_template: Optional[str] = typer.Option(None, "--body-template"),
    body_template_file: Optional[str] = typer.Option(None, "--body-template-file"),
    response_path: Optional[str] = typer.Option(None, "--response-path"),
    tool_calls_path: Optional[str] = typer.Option(None, "--tool-calls-path"),
):
    """Fire one test POST at an HTTP agent endpoint and print the result.

    Pass either --endpoint (to test before saving) or --config-id (to test
    an already-saved HTTP agent). Reports status, latency, detected
    response format, tool_calls count, and the rendered body that was sent.
    """
    client = make_client()
    if config_id is not None:
        emit(client.test_saved_http_agent(config_id), json_output=True)
    elif endpoint:
        template = _read_template_source(body_template, body_template_file)
        emit(
            client.test_http_agent_endpoint(
                http_endpoint=endpoint,
                http_auth_header=auth_header or None,
                http_timeout_seconds=timeout,
                sample_message=message,
                http_body_template=template,
                http_response_path=response_path,
                http_tool_calls_path=tool_calls_path,
            ),
            json_output=True,
        )
    else:
        raise typer.BadParameter("Pass --endpoint <url> or --config-id <id>")


# ── experiments ─────────────────────────────────────────────────────


@app.command("list")
@handle_http_errors
def list_experiments(json_output: bool = typer.Option(False, "--json")):
    """List agent experiments."""
    data = make_client().list_agent_experiments()
    emit(
        data,
        json_output,
        columns=["id", "name", "status", "agent_config_id"],
        title="Agent Experiments",
    )


@app.command("get")
@handle_http_errors
def get(experiment_id: int = typer.Argument(...)):
    """Show one agent experiment."""
    emit(make_client().get_agent_experiment(experiment_id), json_output=True)


@app.command("create")
@handle_http_errors
def create(
    name: str = typer.Option(..., "--name"),
    config_id: int = typer.Option(..., "--config-id", help="Agent config ID."),
    variants: str = typer.Option(..., "--variants", help="CSV of prompt variant IDs."),
    models: str = typer.Option(..., "--models", help="CSV of LLM model names."),
    temperatures: Optional[str] = typer.Option(None, "--temperatures", help="CSV of floats."),
    persona_groups: Optional[str] = typer.Option(None, "--persona-groups", help="CSV strings."),
    scenario_types: Optional[str] = typer.Option(None, "--scenario-types", help="CSV strings."),
    max_turns: Optional[str] = typer.Option(None, "--max-turns", help="CSV ints."),
    description: str = typer.Option("", "--description"),
):
    """Create an agent experiment with a grid-search configuration."""
    emit(
        make_client().create_agent_experiment(
            name=name,
            agent_config_id=config_id,
            prompt_variant_ids=parse_csv_ints(variants) or [],
            llm_models=parse_csv_strs(models) or [],
            temperatures=parse_csv_floats(temperatures),
            persona_group_names=parse_csv_strs(persona_groups),
            scenario_types=parse_csv_strs(scenario_types),
            max_turns=parse_csv_ints(max_turns),
            description=description,
        ),
        json_output=True,
    )


@app.command("run")
@handle_http_errors
def run(experiment_id: int = typer.Argument(...)):
    """Start running an agent experiment."""
    emit(make_client().run_agent_experiment(experiment_id), json_output=True)


@app.command("stop")
@handle_http_errors
def stop(experiment_id: int = typer.Argument(...)):
    """Stop a running agent experiment."""
    emit(make_client().stop_agent_experiment(experiment_id), json_output=True)


@app.command("status")
@handle_http_errors
def status(experiment_id: int = typer.Argument(...)):
    """Get current status (combinations done/total/failed)."""
    emit(make_client().get_agent_experiment_status(experiment_id), json_output=True)


@app.command("results")
@handle_http_errors
def results(experiment_id: int = typer.Argument(...)):
    """Get aggregated results, ranked by score."""
    emit(make_client().get_agent_experiment_results(experiment_id), json_output=True)


@app.command("report")
@handle_http_errors
def report(
    experiment_id: int = typer.Argument(...),
    generate: bool = typer.Option(
        False, "--generate", help="Generate a fresh report (instead of fetching the cached one)."
    ),
):
    """Fetch (or generate) the LLM-powered improvement report."""
    client = make_client()
    if generate:
        emit(client.generate_agent_experiment_report(experiment_id), json_output=True)
    else:
        emit(client.get_agent_experiment_report(experiment_id), json_output=True)


@app.command("delete")
@handle_http_errors
def delete(
    experiment_id: int = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y"),
):
    """Delete an agent experiment."""
    if not yes:
        typer.confirm(f"Delete agent experiment {experiment_id}?", abort=True)
    emit(make_client().delete_agent_experiment(experiment_id), json_output=True)
