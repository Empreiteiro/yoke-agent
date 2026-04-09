"""
Database models for the Agent Evaluation Pipeline.

Covers: agent configuration, prompt variants, scenarios, personas,
interaction datasets, experiments, simulation runs, transcripts, and metrics.
"""
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Float, JSON, ForeignKey, Boolean, func,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


# ── Agent Configuration ───────────────────────────────────────────────


class AgentConfig(Base):
    """An agent definition: system prompt, tools, and behavioral constraints."""
    __tablename__ = "agent_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    system_prompt = Column(Text, nullable=False)
    tools = Column(JSON, default=list)           # [{name, description, parameters}]
    constraints = Column(JSON, default=list)     # ["Never share pricing", ...]
    variables = Column(JSON, default=dict)       # {var_name: description}
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    prompt_variants = relationship("PromptVariant", back_populates="agent_config", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="agent_config", cascade="all, delete-orphan")
    personas = relationship("Persona", back_populates="agent_config", cascade="all, delete-orphan")


class PromptVariant(Base):
    """A variation of the agent's system prompt for A/B testing."""
    __tablename__ = "prompt_variants"

    id = Column(Integer, primary_key=True, index=True)
    agent_config_id = Column(Integer, ForeignKey("agent_configs.id"), nullable=False)
    variant_name = Column(String(255), nullable=False)
    system_prompt = Column(Text, nullable=False)
    description = Column(Text)
    is_original = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    agent_config = relationship("AgentConfig", back_populates="prompt_variants")


# ── Scenarios (Test Cases) ────────────────────────────────────────────


class Scenario(Base):
    """A test case for evaluating the agent.

    The `objective` describes WHAT the user wants to accomplish (the goal).
    The persona's LLM simulator uses this objective + its traits to generate
    the actual user message at runtime. `input_hint` is an optional example
    of how a user might phrase the request (used as fallback when no persona).
    """
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    agent_config_id = Column(Integer, ForeignKey("agent_configs.id"), nullable=False)
    scenario_type = Column(String(50), nullable=False)  # tool_use, decision_path, response_quality, guardrail
    name = Column(String(255), nullable=False)
    description = Column(Text)
    objective = Column(Text, nullable=False)             # WHAT the user wants to achieve
    input_hint = Column(Text)                            # optional example phrasing (fallback when no persona)
    input_message = Column(Text, default="")             # legacy column kept for SQLite compatibility
    expected_output = Column(JSON, nullable=False)       # type-specific schema
    context = Column(Text)                               # optional background info for the scenario
    conversation_history = Column(JSON)                  # optional multi-turn context
    tags = Column(JSON, default=list)
    is_manual = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    agent_config = relationship("AgentConfig", back_populates="scenarios")

    def __init__(self, **kwargs):
        # Auto-populate legacy input_message from objective for SQLite compatibility
        if "input_message" not in kwargs or not kwargs["input_message"]:
            kwargs["input_message"] = kwargs.get("objective", "")
        super().__init__(**kwargs)


# ── Personas ──────────────────────────────────────────────────────────


class Persona(Base):
    """A synthetic user profile for simulated interactions."""
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    agent_config_id = Column(Integer, ForeignKey("agent_configs.id"), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(255))
    description = Column(Text)
    expertise_level = Column(String(50), default="intermediate")  # novice, intermediate, advanced, expert
    communication_style = Column(String(100))                     # formal, casual, terse, verbose, technical
    behavioral_traits = Column(JSON, default=list)                # ["impatient", "detail-oriented", ...]
    language = Column(String(20), default="en")
    goals = Column(JSON, default=list)
    custom_attributes = Column(JSON, default=dict)
    group_name = Column(String(255))                              # audience cohort
    interaction_count = Column(Integer, default=10)
    is_manual = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    agent_config = relationship("AgentConfig", back_populates="personas")


# ── Interaction Datasets (reusable, like RAG datasets) ────────────────


class InteractionDataset(Base):
    """A reusable collection of interaction test cases."""
    __tablename__ = "interaction_datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    agent_config_id = Column(Integer, ForeignKey("agent_configs.id"), nullable=True)
    interaction_mode = Column(String(20), default="single_turn")  # single_turn, multi_turn, mixed
    status = Column(String(50), default="draft")                  # draft, generating, ready, error
    error_message = Column(Text)
    total_items = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    items = relationship("InteractionDatasetItem", back_populates="dataset", cascade="all, delete-orphan")


class InteractionDatasetItem(Base):
    """One interaction test case — single-turn or multi-turn.

    `objective` comes from the scenario. `generated_input` is the actual
    message produced by the persona simulator (or input_hint as fallback).
    """
    __tablename__ = "interaction_dataset_items"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("interaction_datasets.id"), nullable=False)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=True)
    interaction_mode = Column(String(20), nullable=False)   # single_turn, multi_turn
    objective = Column(Text, nullable=False)                # from scenario: what the user wants
    generated_input = Column(Text)                          # actual message (generated by persona simulator or manual)
    input_message = Column(Text, default="")                # legacy column kept for SQLite compatibility
    expected_output = Column(JSON)                          # type-specific
    conversation_history = Column(JSON)                     # full message list for multi-turn
    metadata_ = Column("metadata", JSON, default=dict)     # {scenario_type, persona_name, tags}
    is_manual = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    dataset = relationship("InteractionDataset", back_populates="items")

    def __init__(self, **kwargs):
        if "input_message" not in kwargs or not kwargs["input_message"]:
            kwargs["input_message"] = kwargs.get("objective", "")
        super().__init__(**kwargs)


# ── Agent Experiments ─────────────────────────────────────────────────


class AgentExperiment(Base):
    """An agent evaluation experiment with grid search over prompt × model × temp."""
    __tablename__ = "agent_experiments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    agent_config_id = Column(Integer, ForeignKey("agent_configs.id"), nullable=False)
    dataset_id = Column(Integer, ForeignKey("interaction_datasets.id"), nullable=True)
    grid_config = Column(JSON)  # AgentGridSearchConfig as JSON
    status = Column(String(50), default="pending")  # pending, configured, running, completed, failed, stopped
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    combinations = relationship("AgentExperimentCombination", back_populates="experiment", cascade="all, delete-orphan")
    simulation_runs = relationship("SimulationRun", back_populates="experiment", cascade="all, delete-orphan")


class AgentExperimentCombination(Base):
    """One specific configuration in the agent grid search."""
    __tablename__ = "agent_experiment_combinations"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("agent_experiments.id"), nullable=False)
    params = Column(JSON, nullable=False)  # {prompt_variant_id, model, temperature, persona_group, max_turns, ...}
    status = Column(String(50), default="pending")
    # Aggregated metrics
    aggregated_metrics = Column(JSON)           # {metric: {mean, median, std, min, max}}
    metrics_by_scenario_type = Column(JSON)     # {scenario_type: {metric: score}}
    metrics_by_persona_group = Column(JSON)     # {group: {metric: score}}
    overall_score = Column(Float)
    # Counters
    total_simulations = Column(Integer, default=0)
    completed_simulations = Column(Integer, default=0)
    failed_simulations = Column(Integer, default=0)
    # Token usage
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    # Timing
    duration_seconds = Column(Float)
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)

    experiment = relationship("AgentExperiment", back_populates="combinations")
    transcripts = relationship("SimulationTranscript", back_populates="combination", cascade="all, delete-orphan")


# ── Simulation Runs & Transcripts ─────────────────────────────────────


class SimulationRun(Base):
    """One execution run of an agent experiment."""
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("agent_experiments.id"), nullable=False)
    dataset_id = Column(Integer, ForeignKey("interaction_datasets.id"), nullable=True)
    status = Column(String(50), default="pending")  # pending, running, completed, failed, stopped
    total_simulations = Column(Integer, default=0)
    completed_simulations = Column(Integer, default=0)
    failed_simulations = Column(Integer, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    experiment = relationship("AgentExperiment", back_populates="simulation_runs")


class SimulationTranscript(Base):
    """One simulated conversation (single-turn or multi-turn) with full history."""
    __tablename__ = "simulation_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    combination_id = Column(Integer, ForeignKey("agent_experiment_combinations.id"), nullable=False)
    run_id = Column(Integer, ForeignKey("simulation_runs.id"), nullable=True)
    dataset_item_id = Column(Integer, ForeignKey("interaction_dataset_items.id"), nullable=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=True)
    interaction_index = Column(Integer, default=0)
    interaction_mode = Column(String(20), nullable=False)  # single_turn, multi_turn
    messages = Column(JSON, nullable=False)                # [{role, content, tool_calls?, timestamp}]
    tool_invocations = Column(JSON, default=list)          # [{tool_name, args, mock_response, timestamp}]
    turns = Column(Integer, default=0)
    terminated_by = Column(String(50))                     # max_turns, user_done, agent_done, error
    duration_ms = Column(Integer)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    combination = relationship("AgentExperimentCombination", back_populates="transcripts")


# ── Simulation Metrics ────────────────────────────────────────────────


class SimulationMetrics(Base):
    """Per-transcript evaluation scores."""
    __tablename__ = "simulation_metrics"

    id = Column(Integer, primary_key=True, index=True)
    transcript_id = Column(Integer, ForeignKey("simulation_transcripts.id"), nullable=False)
    scenario_type = Column(String(50))
    metrics = Column(JSON, nullable=False)           # {metric_name: score}
    g_eval_details = Column(JSON)                    # {rubric, reasoning} for G-Eval metrics
    evaluated_at = Column(DateTime, server_default=func.now())
