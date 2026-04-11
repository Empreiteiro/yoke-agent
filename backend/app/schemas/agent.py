"""Pydantic schemas for the Agent Evaluation Pipeline."""
from pydantic import BaseModel, Field, model_validator
from typing import Literal, Optional
from datetime import datetime


# ── Agent Config ──────────────────────────────────────────────────────


AgentType = Literal["builtin", "http"]


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Optional[dict] = None  # JSON Schema


class AgentConfigCreate(BaseModel):
    name: str
    description: Optional[str] = None
    # system_prompt is required for built-in agents, optional for HTTP agents
    system_prompt: Optional[str] = None
    tools: list[ToolDefinition] = []
    constraints: list[str] = []
    variables: dict = {}
    metadata: dict = {}
    # External HTTP agent (issue #169)
    agent_type: AgentType = "builtin"
    http_endpoint: Optional[str] = None
    http_auth_header: Optional[str] = None
    http_timeout_seconds: int = Field(60, ge=1, le=600)

    @model_validator(mode="after")
    def _validate_agent_type(self):
        if self.agent_type == "builtin":
            if not self.system_prompt or not self.system_prompt.strip():
                raise ValueError("system_prompt is required for built-in agents")
        elif self.agent_type == "http":
            if not self.http_endpoint or not self.http_endpoint.strip():
                raise ValueError("http_endpoint is required for external HTTP agents")
            if not self.http_endpoint.startswith(("http://", "https://")):
                raise ValueError("http_endpoint must start with http:// or https://")
        return self


class AgentConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[list[ToolDefinition]] = None
    constraints: Optional[list[str]] = None
    variables: Optional[dict] = None
    metadata: Optional[dict] = None
    agent_type: Optional[AgentType] = None
    http_endpoint: Optional[str] = None
    http_auth_header: Optional[str] = None
    http_timeout_seconds: Optional[int] = Field(None, ge=1, le=600)


class AgentConfigResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    system_prompt: Optional[str]
    tools: list
    constraints: list
    variables: dict
    metadata: dict
    agent_type: AgentType = "builtin"
    http_endpoint: Optional[str] = None
    http_auth_header: Optional[str] = None  # returned so UI can show it (consider masking upstream)
    http_timeout_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    prompt_variant_count: int = 0
    scenario_count: int = 0
    persona_count: int = 0

    class Config:
        from_attributes = True


# ── External HTTP agent test ───────────────────────────────────────────


class TestHttpAgentRequest(BaseModel):
    """Ad-hoc connectivity test for an HTTP endpoint (used before saving)."""
    http_endpoint: str
    http_auth_header: Optional[str] = None
    http_timeout_seconds: int = Field(30, ge=1, le=300)
    sample_message: str = "Hello, this is a connection test from Yoke Agent."


class TestHttpAgentResponse(BaseModel):
    ok: bool
    status_code: Optional[int] = None
    response_preview: Optional[str] = None
    detected_format: Optional[str] = None  # "native" | "openai" | "text"
    tool_calls_detected: int = 0
    latency_ms: Optional[int] = None
    error: Optional[str] = None


# ── Prompt Variants ───────────────────────────────────────────────────


class PromptVariantCreate(BaseModel):
    variant_name: str
    system_prompt: str
    description: Optional[str] = None
    is_original: bool = False


class PromptVariantResponse(BaseModel):
    id: int
    agent_config_id: int
    variant_name: str
    system_prompt: str
    description: Optional[str]
    is_original: bool
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateVariantsRequest(BaseModel):
    count: int = 3
    focus: Optional[str] = None  # e.g., "conciseness", "detail", "tone"


# ── Scenarios ─────────────────────────────────────────────────────────


class ScenarioCreate(BaseModel):
    scenario_type: str  # tool_use, decision_path, response_quality, guardrail
    name: str
    description: Optional[str] = None
    objective: str                           # WHAT the user wants to accomplish
    input_hint: Optional[str] = None         # optional example phrasing
    expected_output: dict
    context: Optional[str] = None            # background info for the scenario
    conversation_history: Optional[list] = None
    tags: list[str] = []
    is_manual: bool = False


class ScenarioUpdate(BaseModel):
    scenario_type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    objective: Optional[str] = None
    input_hint: Optional[str] = None
    expected_output: Optional[dict] = None
    context: Optional[str] = None
    conversation_history: Optional[list] = None
    tags: Optional[list[str]] = None


class ScenarioResponse(BaseModel):
    id: int
    agent_config_id: int
    scenario_type: str
    name: str
    description: Optional[str]
    objective: str
    input_hint: Optional[str]
    expected_output: dict
    context: Optional[str]
    conversation_history: Optional[list]
    tags: list
    is_manual: bool
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateScenariosRequest(BaseModel):
    scenario_type: str
    count: int = 5


# ── Personas ──────────────────────────────────────────────────────────


class PersonaCreate(BaseModel):
    name: str
    role: Optional[str] = None
    description: Optional[str] = None
    expertise_level: str = "intermediate"
    communication_style: Optional[str] = None
    behavioral_traits: list[str] = []
    language: str = "en"
    goals: list[str] = []
    custom_attributes: dict = {}
    group_name: Optional[str] = None
    interaction_count: int = 10
    is_manual: bool = False


class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    expertise_level: Optional[str] = None
    communication_style: Optional[str] = None
    behavioral_traits: Optional[list[str]] = None
    language: Optional[str] = None
    goals: Optional[list[str]] = None
    custom_attributes: Optional[dict] = None
    group_name: Optional[str] = None
    interaction_count: Optional[int] = None


class PersonaResponse(BaseModel):
    id: int
    agent_config_id: int
    name: str
    role: Optional[str]
    description: Optional[str]
    expertise_level: str
    communication_style: Optional[str]
    behavioral_traits: list
    language: str
    goals: list
    custom_attributes: dict
    group_name: Optional[str]
    interaction_count: int
    is_manual: bool
    created_at: datetime

    class Config:
        from_attributes = True


class GeneratePersonasRequest(BaseModel):
    audience_description: str
    count: int = 5
    interaction_count: int = 10


# ── Interaction Datasets ──────────────────────────────────────────────


class InteractionDatasetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    agent_config_id: Optional[int] = None
    interaction_mode: str = "single_turn"  # single_turn, multi_turn, mixed


class InteractionDatasetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    agent_config_id: Optional[int]
    interaction_mode: str
    status: str
    error_message: Optional[str]
    total_items: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InteractionDatasetItemCreate(BaseModel):
    scenario_id: Optional[int] = None
    persona_id: Optional[int] = None
    interaction_mode: str = "single_turn"
    objective: str
    generated_input: Optional[str] = None
    expected_output: Optional[dict] = None
    conversation_history: Optional[list] = None
    metadata: dict = {}
    is_manual: bool = False


class InteractionDatasetItemResponse(BaseModel):
    id: int
    dataset_id: int
    scenario_id: Optional[int]
    persona_id: Optional[int]
    interaction_mode: str
    objective: str
    generated_input: Optional[str]
    expected_output: Optional[dict]
    conversation_history: Optional[list]
    metadata: dict
    is_manual: bool
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateDatasetRequest(BaseModel):
    agent_config_id: int
    name: str
    description: Optional[str] = None
    interaction_mode: str = "single_turn"
    scenario_ids: Optional[list[int]] = None   # None = all scenarios
    persona_ids: Optional[list[int]] = None    # None = all personas


# ── Agent Experiments ─────────────────────────────────────────────────


class AgentGridSearchConfig(BaseModel):
    prompt_variant_ids: list[int]
    llm_models: list[str]
    temperatures: list[float] = [0.0]
    persona_group_names: list[str] = []         # empty = all
    scenario_types: list[str] = []              # empty = all
    max_turns: list[int] = [1]
    interaction_count_override: Optional[int] = None


class AgentExperimentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    agent_config_id: int
    dataset_id: Optional[int] = None
    grid_config: AgentGridSearchConfig


class AgentExperimentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    agent_config_id: int
    dataset_id: Optional[int]
    grid_config: Optional[dict]
    status: str
    created_at: datetime
    updated_at: datetime
    combination_count: int = 0

    class Config:
        from_attributes = True


class AgentCombinationResponse(BaseModel):
    id: int
    experiment_id: int
    params: dict
    status: str
    aggregated_metrics: Optional[dict]
    metrics_by_scenario_type: Optional[dict]
    metrics_by_persona_group: Optional[dict]
    overall_score: Optional[float]
    total_simulations: int
    completed_simulations: int
    failed_simulations: int
    total_tokens: int
    total_cost: float
    duration_seconds: Optional[float]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Simulation ────────────────────────────────────────────────────────


class SimulationTranscriptResponse(BaseModel):
    id: int
    combination_id: int
    run_id: Optional[int]
    dataset_item_id: Optional[int]
    scenario_id: Optional[int]
    persona_id: Optional[int]
    interaction_index: int
    interaction_mode: str
    messages: list
    tool_invocations: list
    turns: int
    terminated_by: Optional[str]
    duration_ms: Optional[int]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    created_at: datetime

    class Config:
        from_attributes = True


class SimulationMetricsResponse(BaseModel):
    id: int
    transcript_id: int
    scenario_type: Optional[str]
    metrics: dict
    g_eval_details: Optional[dict]
    evaluated_at: datetime

    class Config:
        from_attributes = True
