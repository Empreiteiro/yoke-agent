"""
Simulation engine: runs conversations between a user-simulator LLM and the agent-under-test.
Supports single-turn and multi-turn interactions.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.models.agent import (
    AgentConfig, PromptVariant, Scenario, Persona,
    AgentExperiment, AgentExperimentCombination,
    InteractionDatasetItem, SimulationTranscript,
)
from app.services.llm_factory import get_llm

import subprocess as _subprocess

logger = logging.getLogger(__name__)


def _kill_orphan_claude_processes():
    """Kill any claude CLI subprocess that was started by this backend and is still running."""
    try:
        result = _subprocess.run(
            ["pgrep", "-f", "claude.*-p.*output-format text"],
            capture_output=True, text=True, timeout=5,
        )
        for pid in result.stdout.strip().split("\n"):
            if pid.strip():
                try:
                    os.kill(int(pid.strip()), 9)
                    logger.info(f"Killed orphan claude process {pid.strip()}")
                except (ProcessLookupError, ValueError):
                    pass
    except Exception:
        pass

USER_SIMULATOR_PROMPT = """\
You are simulating a user with this profile:
- Name: {name}
- Role: {role}
- Expertise: {expertise_level}
- Communication style: {communication_style}
- Traits: {traits}
- Goals: {goals}

Your OBJECTIVE in this conversation: {objective}
{context_line}

Instructions:
- Write your opening message to the agent as this persona would naturally phrase it
- Stay in character throughout the conversation
- Respond naturally based on the agent's replies
- If the agent asks clarifying questions, answer based on your persona
- Signal completion by including [TASK_COMPLETE] if the agent successfully helped you
- Signal failure by including [TASK_FAILED] if the agent cannot help after reasonable attempts
- Keep responses concise and realistic for your persona

Write ONLY your message to the agent, nothing else.
"""

GENERATE_INPUT_PROMPT = """\
You are simulating a user with this profile:
- Role: {role}
- Expertise: {expertise_level}
- Communication style: {communication_style}
- Traits: {traits}

Write a single message to an AI agent to accomplish this objective: {objective}
{context_line}

Write ONLY the user's message, nothing else. Stay in character.
"""


async def run_simulation(
    db: Session,
    experiment: AgentExperiment,
    combination: AgentExperimentCombination,
):
    """Run all simulations for a single combination."""
    params = combination.params
    config = db.query(AgentConfig).filter(AgentConfig.id == experiment.agent_config_id).first()
    variant = db.query(PromptVariant).filter(PromptVariant.id == params["prompt_variant_id"]).first()

    if not config or not variant:
        raise ValueError("Agent config or prompt variant not found")

    # Get dataset items (or build from scenarios × personas)
    items = []
    if experiment.dataset_id:
        items = db.query(InteractionDatasetItem).filter(
            InteractionDatasetItem.dataset_id == experiment.dataset_id
        ).all()
    else:
        # Build items dynamically from scenarios × personas
        sq = db.query(Scenario).filter(Scenario.agent_config_id == config.id)
        if params.get("scenario_types"):
            sq = sq.filter(Scenario.scenario_type.in_(params["scenario_types"]))
        scenarios = sq.all()

        pq = db.query(Persona).filter(Persona.agent_config_id == config.id)
        if params.get("persona_group_names"):
            pq = pq.filter(Persona.group_name.in_(params["persona_group_names"]))
        personas = pq.all()

        logger.info(
            f"Combo {combination.id}: found {len(scenarios)} scenarios, {len(personas)} personas "
            f"for config {config.id} (filters: types={params.get('scenario_types')}, groups={params.get('persona_group_names')})"
        )

        if not scenarios:
            raise ValueError(
                f"No scenarios found for agent config '{config.name}' (id={config.id}). "
                "Please create scenarios in the 'Create Scenarios' step before running."
            )
        if not personas:
            raise ValueError(
                f"No personas found for agent config '{config.name}' (id={config.id}). "
                "Please create personas in the 'Create Personas' step before running."
            )

        for scenario in scenarios:
            for persona in personas:
                items.append(type("Item", (), {
                    "id": None,
                    "scenario_id": scenario.id,
                    "persona_id": persona.id,
                    "interaction_mode": "multi_turn" if params.get("max_turns", 1) > 1 else "single_turn",
                    "objective": scenario.objective,
                    "input_hint": scenario.input_hint,
                    "expected_output": scenario.expected_output,
                    "context": scenario.context,
                })())

    max_turns = params.get("max_turns", 1)
    model = params.get("model", "claude-code")
    temperature = params.get("temperature", 0.0)
    interaction_count_override = params.get("interaction_count_override")

    # Pre-fetch scenarios and personas to avoid repeated queries
    scenario_map = {}
    persona_map = {}
    for item in items:
        if item.scenario_id and item.scenario_id not in scenario_map:
            scenario_map[item.scenario_id] = db.query(Scenario).filter(Scenario.id == item.scenario_id).first()
        if item.persona_id and item.persona_id not in persona_map:
            persona_map[item.persona_id] = db.query(Persona).filter(Persona.id == item.persona_id).first()

    # Calculate total: each persona has its own interaction_count (multiplier),
    # unless overridden globally by the grid config
    total = 0
    for item in items:
        persona = persona_map.get(item.persona_id)
        reps = interaction_count_override or (persona.interaction_count if persona else 1) or 1
        total += reps

    completed = 0
    failed = 0

    # Update combination with total count immediately so the UI can show progress
    combination.total_simulations = total
    combination.completed_simulations = 0
    combination.failed_simulations = 0
    db.commit()

    # Build flat list of simulation tasks
    simulation_tasks = []
    for item in items:
        scenario = scenario_map.get(item.scenario_id)
        persona = persona_map.get(item.persona_id)
        interaction_count = interaction_count_override or (persona.interaction_count if persona else 1) or 1
        for interaction_idx in range(interaction_count):
            simulation_tasks.append({
                "scenario": scenario,
                "persona": persona,
                "item": item,
                "interaction_idx": interaction_idx,
            })

    logger.info(f"Combo {combination.id}: starting {len(simulation_tasks)} simulations ({len(items)} items, max_turns={max_turns})")

    # Concurrency: run up to N simulations in parallel
    # Each simulation uses subprocess — Claude CLI handles up to ~8 concurrent calls fine
    MAX_CONCURRENCY = 4
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    completed_count = [0]  # mutable for closure
    failed_count = [0]
    progress_lock = asyncio.Lock()

    async def run_one(task: dict) -> SimulationTranscript:
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    _run_single_conversation(
                        db=db,
                        combination=combination,
                        variant=variant,
                        scenario=task["scenario"],
                        persona=task["persona"],
                        item=task["item"],
                        interaction_idx=task["interaction_idx"],
                        max_turns=max_turns,
                        model=model,
                        temperature=temperature,
                    ),
                    timeout=180,  # 3 minutes max per simulation
                )
            except asyncio.TimeoutError:
                logger.warning(f"Simulation timed out: scenario={task['scenario'].id if task['scenario'] else '?'} persona={task['persona'].id if task['persona'] else '?'}")
                _kill_orphan_claude_processes()
                return SimulationTranscript(
                    combination_id=combination.id,
                    dataset_item_id=getattr(task["item"], "id", None),
                    scenario_id=getattr(task["item"], "scenario_id", None),
                    persona_id=getattr(task["item"], "persona_id", None),
                    interaction_index=task["interaction_idx"],
                    interaction_mode="single_turn" if max_turns <= 1 else "multi_turn",
                    messages=[{"role": "system", "content": "Simulation timed out after 180 seconds"}],
                    terminated_by="timeout",
                    turns=0,
                    duration_ms=180000,
                )
            except Exception as e:
                logger.warning(f"Simulation failed: {type(e).__name__}: {e}")
                return SimulationTranscript(
                    combination_id=combination.id,
                    dataset_item_id=getattr(task["item"], "id", None),
                    scenario_id=getattr(task["item"], "scenario_id", None),
                    persona_id=getattr(task["item"], "persona_id", None),
                    interaction_index=task["interaction_idx"],
                    interaction_mode="single_turn" if max_turns <= 1 else "multi_turn",
                    messages=[{"role": "system", "content": f"Error: {type(e).__name__}: {str(e)[:200]}"}],
                    terminated_by="error",
                    turns=0,
                    duration_ms=0,
                )

    async def run_and_track(task: dict):
        transcript = await run_one(task)
        async with progress_lock:
            if transcript.terminated_by in ("error", "timeout"):
                failed_count[0] += 1
            else:
                completed_count[0] += 1
            # Only add/commit if it's a new transcript (not persisted yet)
            if transcript.id is None:
                db.add(transcript)
            combination.completed_simulations = completed_count[0]
            combination.failed_simulations = failed_count[0]
            db.commit()
            logger.info(f"Combo {combination.id} progress: {completed_count[0] + failed_count[0]}/{len(simulation_tasks)}")
        return transcript

    # Run all simulations concurrently (limited by semaphore)
    await asyncio.gather(*[run_and_track(task) for task in simulation_tasks])

    # Aggregate tokens and cost from all transcripts of this combination
    agg = db.query(
        sqlfunc.sum(SimulationTranscript.total_tokens),
        sqlfunc.sum(SimulationTranscript.prompt_tokens),
        sqlfunc.sum(SimulationTranscript.completion_tokens),
    ).filter(SimulationTranscript.combination_id == combination.id).first()
    total_tokens = int(agg[0] or 0) if agg else 0
    # Estimate cost at ~$0 for claude-code CLI (local); $3/M input + $15/M output for API providers
    # For now, use a rough estimate based on model name
    cost_per_m_input = {"gpt-4o": 2.5, "gpt-4o-mini": 0.15, "claude-opus-4": 15.0, "claude-sonnet-4": 3.0}.get(model, 0.0)
    cost_per_m_output = {"gpt-4o": 10.0, "gpt-4o-mini": 0.6, "claude-opus-4": 75.0, "claude-sonnet-4": 15.0}.get(model, 0.0)
    est_cost = ((agg[1] or 0) * cost_per_m_input + (agg[2] or 0) * cost_per_m_output) / 1_000_000 if agg else 0.0

    combination.total_simulations = len(simulation_tasks)
    combination.completed_simulations = completed_count[0]
    combination.failed_simulations = failed_count[0]
    combination.total_tokens = total_tokens
    combination.total_cost = round(est_cost, 6)
    db.commit()
    logger.info(f"Combo {combination.id}: finished — {completed_count[0]} completed, {failed_count[0]} failed, {total_tokens} tokens, ${est_cost:.4f}")


async def _run_single_conversation(
    db: Session,
    combination: AgentExperimentCombination,
    variant: PromptVariant,
    scenario: Scenario | None,
    persona: Persona | None,
    item,
    interaction_idx: int,
    max_turns: int,
    model: str,
    temperature: float,
) -> SimulationTranscript:
    """Execute one conversation between user-simulator and agent-under-test."""
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    start_time = time.time()

    # Agent LLM
    agent_llm = get_llm(db, model=model, temperature=temperature)

    # Build agent messages
    agent_messages = [SystemMessage(content=variant.system_prompt)]

    # Messages history for recording
    recorded_messages = []
    tool_invocations = []

    # Generate the initial user message from objective + persona
    objective = getattr(item, "objective", None) or (scenario.objective if scenario else "")
    input_hint = getattr(item, "input_hint", None) or (scenario.input_hint if scenario else None)
    context = getattr(item, "context", None) or (scenario.context if scenario else None)

    PER_CALL_TIMEOUT = 60  # seconds per LLM call

    if persona and objective:
        # Use LLM to generate the opening message as this persona would say it
        user_message = await asyncio.wait_for(
            _generate_persona_message(db, persona, objective, context),
            timeout=PER_CALL_TIMEOUT,
        )
    elif input_hint:
        # Fallback to the hint if no persona
        user_message = input_hint
    else:
        # Last resort: use objective as-is
        user_message = objective

    terminated_by = "max_turns"
    turns = 0

    try:
      for turn in range(max_turns):
        turns = turn + 1

        # Record user message
        recorded_messages.append({
            "role": "user",
            "content": user_message,
            "turn": turns,
            "timestamp": datetime.utcnow().isoformat(),
        })
        agent_messages.append(HumanMessage(content=user_message))

        # Agent responds (with per-call timeout)
        agent_response = await asyncio.wait_for(
            agent_llm.ainvoke(agent_messages),
            timeout=PER_CALL_TIMEOUT,
        )
        agent_text = agent_response.content if hasattr(agent_response, "content") else str(agent_response)

        recorded_messages.append({
            "role": "assistant",
            "content": agent_text,
            "turn": turns,
            "timestamp": datetime.utcnow().isoformat(),
        })
        agent_messages.append(AIMessage(content=agent_text))

        # Check for tool calls (simple heuristic — can be enhanced)
        if scenario and scenario.scenario_type == "tool_use":
            expected = scenario.expected_output or {}
            tool_name = expected.get("tool_name")
            if tool_name and tool_name.lower() in agent_text.lower():
                tool_invocations.append({
                    "tool_name": tool_name,
                    "detected_in_response": True,
                    "turn": turns,
                })

        # Single-turn: stop after one exchange
        if max_turns <= 1:
            terminated_by = "single_turn"
            break

        # Multi-turn: use user simulator to generate follow-up
        if persona and turn < max_turns - 1:
            follow_up = await asyncio.wait_for(
                _simulate_user_followup(
                    db, persona, scenario, agent_text, recorded_messages,
                ),
                timeout=PER_CALL_TIMEOUT,
            )
            if "[TASK_COMPLETE]" in follow_up:
                terminated_by = "user_done"
                recorded_messages.append({
                    "role": "user",
                    "content": follow_up,
                    "turn": turns + 1,
                    "timestamp": datetime.utcnow().isoformat(),
                    "signal": "TASK_COMPLETE",
                })
                break
            elif "[TASK_FAILED]" in follow_up:
                terminated_by = "user_done"
                recorded_messages.append({
                    "role": "user",
                    "content": follow_up,
                    "turn": turns + 1,
                    "timestamp": datetime.utcnow().isoformat(),
                    "signal": "TASK_FAILED",
                })
                break
            user_message = follow_up

    except asyncio.TimeoutError:
        terminated_by = "timeout"
        logger.warning(f"Conversation timed out at turn {turns}")
        recorded_messages.append({
            "role": "system",
            "content": f"Conversation timed out at turn {turns} (>{PER_CALL_TIMEOUT}s per call)",
            "turn": turns,
            "timestamp": datetime.utcnow().isoformat(),
        })
        # Kill any orphaned claude subprocess
        _kill_orphan_claude_processes()

    elapsed_ms = int((time.time() - start_time) * 1000)

    # Estimate tokens (rough)
    total_chars = sum(len(m["content"]) for m in recorded_messages)
    est_tokens = total_chars // 4

    transcript = SimulationTranscript(
        combination_id=combination.id,
        dataset_item_id=getattr(item, "id", None),
        scenario_id=getattr(item, "scenario_id", None),
        persona_id=getattr(item, "persona_id", None),
        interaction_index=interaction_idx,
        interaction_mode="single_turn" if max_turns <= 1 else "multi_turn",
        messages=recorded_messages,
        tool_invocations=tool_invocations,
        turns=turns,
        terminated_by=terminated_by,
        duration_ms=elapsed_ms,
        prompt_tokens=est_tokens // 2,
        completion_tokens=est_tokens // 2,
        total_tokens=est_tokens,
    )
    # Don't commit here — the caller (run_and_track) handles persistence
    # under a lock to avoid race conditions with concurrent simulations
    return transcript


async def _generate_persona_message(
    db: Session,
    persona: Persona,
    objective: str,
    context: str | None = None,
) -> str:
    """Use LLM to generate the opening user message as this persona would phrase it."""
    from langchain_core.messages import HumanMessage as HM

    simulator_llm = get_llm(db, temperature=0.6)
    context_line = f"Background context: {context}" if context else ""

    prompt = GENERATE_INPUT_PROMPT.format(
        role=persona.role or "User",
        expertise_level=persona.expertise_level,
        communication_style=persona.communication_style or "casual",
        traits=", ".join(persona.behavioral_traits or []),
        objective=objective,
        context_line=context_line,
    )

    response = await simulator_llm.ainvoke([HM(content=prompt)])
    return response.content.strip() if hasattr(response, "content") else str(response).strip()


async def _simulate_user_followup(
    db: Session,
    persona: Persona,
    scenario: Scenario | None,
    agent_response: str,
    conversation_history: list[dict],
) -> str:
    """Use a capable LLM to simulate the user's next message in a multi-turn conversation."""
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    simulator_llm = get_llm(db, temperature=0.6)
    objective = scenario.objective if scenario else "General interaction"
    context_line = f"Background context: {scenario.context}" if scenario and scenario.context else ""

    system_prompt = USER_SIMULATOR_PROMPT.format(
        name=persona.name,
        role=persona.role or "User",
        expertise_level=persona.expertise_level,
        communication_style=persona.communication_style or "casual",
        traits=", ".join(persona.behavioral_traits or []),
        goals=", ".join(persona.goals or []),
        objective=objective,
        context_line=context_line,
    )

    messages = [SystemMessage(content=system_prompt)]
    for msg in conversation_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(
        content=f"The agent just replied: \"{agent_response[:500]}\"\n\nWhat is your next message as this persona? If the task is done, include [TASK_COMPLETE]. If the agent failed, include [TASK_FAILED]."
    ))

    response = await simulator_llm.ainvoke(messages)
    return response.content if hasattr(response, "content") else str(response)
