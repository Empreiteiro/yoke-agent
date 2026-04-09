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
    {"name": "get_token_usage_summary", "description": "Get token usage summary with breakdowns", "group": "Token Usage"},
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
