"""MCP Server configuration routes."""

import json
import logging
from pathlib import Path
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "mcp_config.json"
SERVER_PATH = Path(__file__).parent.parent.parent / "mcp_server.py"

MCP_TOOL_REGISTRY = [
    {"name": "list_documents", "description": "List all uploaded documents", "group": "Documents"},
    {"name": "upload_document", "description": "Upload a document file (PDF, TXT, DOCX, MD)", "group": "Documents"},
    {"name": "list_datasets", "description": "List all evaluation datasets", "group": "Datasets"},
    {"name": "get_dataset", "description": "Get a dataset by ID with all Q&A items", "group": "Datasets"},
    {"name": "create_dataset", "description": "Create a new evaluation dataset from documents", "group": "Datasets"},
    {"name": "generate_dataset", "description": "Generate Q&A pairs for a dataset using LLM", "group": "Datasets"},
    {"name": "approve_dataset", "description": "Approve a dataset for use in experiments", "group": "Datasets"},
    {"name": "list_experiments", "description": "List all experiments with status and scores", "group": "Experiments"},
    {"name": "create_experiment", "description": "Create a new experiment", "group": "Experiments"},
    {"name": "configure_grid_search", "description": "Configure grid search parameters", "group": "Experiments"},
    {"name": "run_experiment", "description": "Start running an experiment", "group": "Experiments"},
    {"name": "stop_experiment", "description": "Stop a running experiment", "group": "Experiments"},
    {"name": "resume_experiment", "description": "Resume a stopped or failed experiment", "group": "Experiments"},
    {"name": "get_experiment", "description": "Get experiment details with combination statuses", "group": "Experiments"},
    {"name": "get_experiment_report", "description": "Get full report with best configuration", "group": "Experiments"},
    {"name": "delete_experiment", "description": "Delete an experiment", "group": "Experiments"},
    {"name": "list_collections", "description": "List saved vectorstore collections", "group": "Collections"},
    {"name": "query_collection", "description": "Query a collection and get an answer", "group": "Collections"},
    {"name": "delete_collection", "description": "Delete a saved collection", "group": "Collections"},
    {"name": "list_providers", "description": "List configured LLM/embedding providers", "group": "Providers"},
    {"name": "get_available_models", "description": "Get all available models from providers", "group": "Providers"},
    {"name": "get_provider_catalog", "description": "Get supported provider types and their known models", "group": "Providers"},
    {"name": "get_provider", "description": "Get a single provider by ID", "group": "Providers"},
    {"name": "create_provider", "description": "Create a new LLM/embedding provider", "group": "Providers"},
    {"name": "update_provider", "description": "Update an existing provider", "group": "Providers"},
    {"name": "delete_provider", "description": "Delete a provider", "group": "Providers"},
    {"name": "test_provider", "description": "Test connectivity for a provider", "group": "Providers"},
    {"name": "get_token_usage_summary", "description": "Get token usage summary with breakdowns", "group": "Token Usage"},
    # ── Agent Workbench ───────────────────────────────────────────────
    {"name": "list_agent_configs", "description": "List all agent configurations", "group": "Agent Workbench"},
    {"name": "get_agent_config", "description": "Get an agent configuration by ID", "group": "Agent Workbench"},
    {"name": "create_agent_config", "description": "Create a new agent configuration", "group": "Agent Workbench"},
    {"name": "update_agent_config", "description": "Update an agent configuration", "group": "Agent Workbench"},
    {"name": "delete_agent_config", "description": "Delete an agent configuration", "group": "Agent Workbench"},
    {"name": "list_prompt_variants", "description": "List prompt variants for an agent config", "group": "Agent Workbench"},
    {"name": "generate_prompt_variants", "description": "LLM-generate prompt variations", "group": "Agent Workbench"},
    {"name": "list_scenarios", "description": "List test scenarios for an agent config", "group": "Agent Workbench"},
    {"name": "generate_scenarios", "description": "LLM-generate test scenarios", "group": "Agent Workbench"},
    {"name": "list_personas", "description": "List synthetic personas for an agent config", "group": "Agent Workbench"},
    {"name": "generate_personas", "description": "LLM-generate synthetic personas", "group": "Agent Workbench"},
    {"name": "list_agent_experiments", "description": "List all agent experiments", "group": "Agent Experiments"},
    {"name": "get_agent_experiment", "description": "Get an agent experiment by ID", "group": "Agent Experiments"},
    {"name": "create_agent_experiment", "description": "Create an agent experiment with grid config", "group": "Agent Experiments"},
    {"name": "run_agent_experiment", "description": "Run an agent experiment", "group": "Agent Experiments"},
    {"name": "stop_agent_experiment", "description": "Stop a running agent experiment", "group": "Agent Experiments"},
    {"name": "get_agent_experiment_status", "description": "Get current status of an agent experiment", "group": "Agent Experiments"},
    {"name": "get_agent_experiment_results", "description": "Get aggregated results ranked by score", "group": "Agent Experiments"},
    {"name": "generate_agent_experiment_report", "description": "Generate an improvement report", "group": "Agent Experiments"},
    {"name": "get_agent_experiment_report", "description": "Fetch a previously-generated report", "group": "Agent Experiments"},
    {"name": "delete_agent_experiment", "description": "Delete an agent experiment", "group": "Agent Experiments"},
]


def _read_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {"disabled_tools": []}


def _write_config(config: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


@router.get("/tools")
def list_mcp_tools():
    config = _read_config()
    disabled = set(config.get("disabled_tools", []))
    tools = [
        {**tool, "enabled": tool["name"] not in disabled}
        for tool in MCP_TOOL_REGISTRY
    ]
    return {"tools": tools}


@router.put("/tools")
def update_mcp_tools(data: dict):
    disabled_tools = data.get("disabled_tools", [])
    _write_config({"disabled_tools": disabled_tools})
    return {"detail": f"Updated MCP config. {len(disabled_tools)} tool(s) disabled."}


@router.get("/connection-info")
def get_connection_info():
    return {
        "server_path": str(SERVER_PATH.resolve()),
        "base_url": "http://localhost:4040",
    }
