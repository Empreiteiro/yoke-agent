"""
Simulation engine: runs conversations between a user-simulator LLM and the agent-under-test.
Supports single-turn and multi-turn interactions.
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.agent import (
    AgentConfig, PromptVariant, Scenario, Persona,
    AgentExperiment, AgentExperimentCombination,
    InteractionDatasetItem, SimulationTranscript,
)
from app.services.llm_factory import get_llm

logger = logging.getLogger(__name__)

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

    logger.info(f"Combo {combination.id}: starting {total} simulations ({len(items)} items, max_turns={max_turns})")

    for idx, item in enumerate(items):
        scenario = scenario_map.get(item.scenario_id)
        persona = persona_map.get(item.persona_id)
        # Per-persona multiplier (or global override)
        interaction_count = interaction_count_override or (persona.interaction_count if persona else 1) or 1

        for interaction_idx in range(interaction_count):
            try:
                transcript = await asyncio.wait_for(
                    _run_single_conversation(
                        db=db,
                        combination=combination,
                        variant=variant,
                        scenario=scenario,
                        persona=persona,
                        item=item,
                        interaction_idx=interaction_idx,
                        max_turns=max_turns,
                        model=model,
                        temperature=temperature,
                    ),
                    timeout=120,  # 2 minutes max per simulation
                )
                completed += 1
            except asyncio.TimeoutError:
                logger.warning(f"Simulation timed out: combo={combination.id} scenario={getattr(item, 'scenario_id', '?')} persona={getattr(item, 'persona_id', '?')}")
                transcript = SimulationTranscript(
                    combination_id=combination.id,
                    dataset_item_id=getattr(item, "id", None),
                    scenario_id=getattr(item, "scenario_id", None),
                    persona_id=getattr(item, "persona_id", None),
                    interaction_index=interaction_idx,
                    interaction_mode="single_turn" if max_turns <= 1 else "multi_turn",
                    messages=[{"role": "system", "content": "Simulation timed out after 120 seconds"}],
                    terminated_by="timeout",
                    turns=0,
                    duration_ms=120000,
                )
                db.add(transcript)
                failed += 1
            except Exception as e:
                logger.warning(f"Simulation failed: {e}")
                transcript = SimulationTranscript(
                    combination_id=combination.id,
                    dataset_item_id=getattr(item, "id", None),
                    scenario_id=getattr(item, "scenario_id", None),
                    persona_id=getattr(item, "persona_id", None),
                    interaction_index=interaction_idx,
                    interaction_mode="single_turn" if max_turns <= 1 else "multi_turn",
                    messages=[],
                    terminated_by="error",
                    turns=0,
                    duration_ms=0,
                )
                db.add(transcript)
                failed += 1

            # Update progress after each simulation so the UI reflects real-time status
            combination.completed_simulations = completed
            combination.failed_simulations = failed
            db.commit()

    combination.total_simulations = completed + failed
    combination.completed_simulations = completed
    combination.failed_simulations = failed
    db.commit()
    logger.info(f"Combo {combination.id}: finished — {completed} completed, {failed} failed")


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

    if persona and objective:
        # Use LLM to generate the opening message as this persona would say it
        user_message = await _generate_persona_message(db, persona, objective, context)
    elif input_hint:
        # Fallback to the hint if no persona
        user_message = input_hint
    else:
        # Last resort: use objective as-is
        user_message = objective

    terminated_by = "max_turns"
    turns = 0

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

        # Agent responds
        agent_response = await agent_llm.ainvoke(agent_messages)
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
            follow_up = await _simulate_user_followup(
                db, persona, scenario, agent_text, recorded_messages,
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
    db.add(transcript)
    db.commit()
    db.refresh(transcript)
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
