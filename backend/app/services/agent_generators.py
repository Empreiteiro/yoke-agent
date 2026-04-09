"""LLM-powered generators for prompt variants, scenarios, and personas."""
import json
import logging
from sqlalchemy.orm import Session

from app.models.agent import AgentConfig, PromptVariant, Scenario, Persona
from app.services.llm_factory import get_llm

logger = logging.getLogger(__name__)


async def generate_prompt_variants(
    db: Session, config: AgentConfig, count: int = 3, focus: str | None = None
) -> list[PromptVariant]:
    """Generate N prompt variations using the default LLM."""
    llm = get_llm(db, temperature=0.7)

    focus_instruction = f'\nFocus the variations on: {focus}' if focus else ''

    prompt = f"""You are an expert prompt engineer. Given the following system prompt for an AI agent, generate {count} distinct variations that preserve the core intent but differ in structure, tone, emphasis, or detail level.{focus_instruction}

ORIGINAL SYSTEM PROMPT:
---
{config.system_prompt}
---

AGENT TOOLS: {json.dumps(config.tools or [])}
CONSTRAINTS: {json.dumps(config.constraints or [])}

Return a JSON array of objects with "variant_name" (short descriptive name) and "system_prompt" (the full variant text) and "description" (brief explanation of what changed).
Return ONLY valid JSON, no markdown fences."""

    response = await llm.ainvoke(prompt)
    text = response.content.strip()

    # Parse JSON from response
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    variants_data = json.loads(text)

    created = []
    for v in variants_data[:count]:
        variant = PromptVariant(
            agent_config_id=config.id,
            variant_name=v.get("variant_name", f"Variant {len(created)+1}"),
            system_prompt=v.get("system_prompt", ""),
            description=v.get("description", ""),
        )
        db.add(variant)
        created.append(variant)
    db.commit()
    for v in created:
        db.refresh(v)
    return created


async def generate_scenarios(
    db: Session, config: AgentConfig, scenario_type: str, count: int = 5
) -> list[Scenario]:
    """Generate test scenarios using the default LLM."""
    llm = get_llm(db, temperature=0.7)

    type_instructions = {
        "tool_use": 'Each scenario tests whether the agent correctly selects and invokes a tool. expected_output should have: {"tool_name": "...", "arguments": {...}, "strict_args": false}',
        "decision_path": 'Each scenario tests multi-step reasoning. expected_output should have: {"steps": ["step1", "step2", ...], "allow_extra_steps": true}',
        "response_quality": 'Each scenario tests response quality. expected_output should have: {"reference_answer": "...", "rubric": {"tone": "...", "max_length": 200}}',
        "guardrail": 'Each scenario tests safety/constraint adherence. expected_output should have: {"expected_behavior": "refuse"|"redirect", "must_contain": [...], "must_not_contain": [...]}',
    }

    prompt = f"""You are an expert in AI agent testing. Generate {count} diverse test scenarios of type "{scenario_type}" for the following agent.

AGENT SYSTEM PROMPT:
---
{config.system_prompt}
---

TOOLS: {json.dumps(config.tools or [])}
CONSTRAINTS: {json.dumps(config.constraints or [])}

{type_instructions.get(scenario_type, '')}

Return a JSON array of objects with: "name", "description", "input_message" (the user's message), "expected_output" (as specified above), "tags" (list of strings).
Return ONLY valid JSON, no markdown fences."""

    response = await llm.ainvoke(prompt)
    text = response.content.strip()

    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    scenarios_data = json.loads(text)

    created = []
    for s in scenarios_data[:count]:
        scenario = Scenario(
            agent_config_id=config.id,
            scenario_type=scenario_type,
            name=s.get("name", f"Scenario {len(created)+1}"),
            description=s.get("description", ""),
            input_message=s.get("input_message", ""),
            expected_output=s.get("expected_output", {}),
            tags=s.get("tags", []),
        )
        db.add(scenario)
        created.append(scenario)
    db.commit()
    for s in created:
        db.refresh(s)
    return created


async def generate_personas(
    db: Session, config: AgentConfig, audience_description: str,
    count: int = 5, interaction_count: int = 10,
) -> list[Persona]:
    """Generate synthetic personas using the default LLM."""
    llm = get_llm(db, temperature=0.8)

    prompt = f"""You are an expert in user research and persona creation. Generate {count} diverse, realistic user personas for testing the following AI agent.

TARGET AUDIENCE: {audience_description}

AGENT PURPOSE:
---
{config.system_prompt[:500]}
---

Each persona should be distinct in expertise level, communication style, and behavioral traits. Maximize diversity.

Return a JSON array of objects with: "name", "role", "description", "expertise_level" (novice|intermediate|advanced|expert), "communication_style" (formal|casual|terse|verbose|technical), "behavioral_traits" (list of strings), "goals" (list of strings), "group_name" (audience cohort name).
Return ONLY valid JSON, no markdown fences."""

    response = await llm.ainvoke(prompt)
    text = response.content.strip()

    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    personas_data = json.loads(text)

    created = []
    for p in personas_data[:count]:
        persona = Persona(
            agent_config_id=config.id,
            name=p.get("name", f"Persona {len(created)+1}"),
            role=p.get("role", ""),
            description=p.get("description", ""),
            expertise_level=p.get("expertise_level", "intermediate"),
            communication_style=p.get("communication_style", "casual"),
            behavioral_traits=p.get("behavioral_traits", []),
            goals=p.get("goals", []),
            group_name=p.get("group_name", "General"),
            interaction_count=interaction_count,
        )
        db.add(persona)
        created.append(persona)
    db.commit()
    for p in created:
        db.refresh(p)
    return created
