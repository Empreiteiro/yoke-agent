"""CRUD endpoints for Agent Configurations, Prompt Variants, Scenarios, and Personas."""
import logging
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.agent import (
    AgentConfig, PromptVariant, Scenario, Persona,
)
from app.schemas.agent import (
    AgentConfigCreate, AgentConfigUpdate, AgentConfigResponse,
    PromptVariantCreate, PromptVariantResponse, GenerateVariantsRequest,
    ScenarioCreate, ScenarioUpdate, ScenarioResponse, GenerateScenariosRequest,
    PersonaCreate, PersonaUpdate, PersonaResponse, GeneratePersonasRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helper ────────────────────────────────────────────────────────────

def _get_config_or_404(db: Session, config_id: int) -> AgentConfig:
    config = db.query(AgentConfig).filter(AgentConfig.id == config_id).first()
    if not config:
        raise HTTPException(404, "Agent config not found")
    return config


# ══════════════════════════════════════════════════════════════════════
#  AGENT CONFIGS
# ══════════════════════════════════════════════════════════════════════

@router.get("/", response_model=list[AgentConfigResponse])
def list_configs(db: Session = Depends(get_db)):
    configs = db.query(AgentConfig).order_by(AgentConfig.updated_at.desc()).all()
    result = []
    for c in configs:
        resp = AgentConfigResponse(
            id=c.id, name=c.name, description=c.description,
            system_prompt=c.system_prompt, tools=c.tools or [],
            constraints=c.constraints or [], variables=c.variables or {},
            metadata=c.metadata_ or {},
            created_at=c.created_at, updated_at=c.updated_at,
            prompt_variant_count=len(c.prompt_variants),
            scenario_count=len(c.scenarios),
            persona_count=len(c.personas),
        )
        result.append(resp)
    return result


@router.post("/", response_model=AgentConfigResponse, status_code=201)
def create_config(body: AgentConfigCreate, db: Session = Depends(get_db)):
    config = AgentConfig(
        name=body.name,
        description=body.description,
        system_prompt=body.system_prompt,
        tools=[t.model_dump() for t in body.tools],
        constraints=body.constraints,
        variables=body.variables,
        metadata_=body.metadata,
    )
    db.add(config)
    db.flush()
    # Auto-create the original prompt as a variant
    original = PromptVariant(
        agent_config_id=config.id,
        variant_name="Original",
        system_prompt=body.system_prompt,
        description="Original system prompt",
        is_original=True,
    )
    db.add(original)
    db.commit()
    db.refresh(config)
    return AgentConfigResponse(
        id=config.id, name=config.name, description=config.description,
        system_prompt=config.system_prompt, tools=config.tools or [],
        constraints=config.constraints or [], variables=config.variables or {},
        metadata=config.metadata_ or {},
        created_at=config.created_at, updated_at=config.updated_at,
        prompt_variant_count=1, scenario_count=0, persona_count=0,
    )


@router.get("/{config_id}", response_model=AgentConfigResponse)
def get_config(config_id: int, db: Session = Depends(get_db)):
    c = _get_config_or_404(db, config_id)
    return AgentConfigResponse(
        id=c.id, name=c.name, description=c.description,
        system_prompt=c.system_prompt, tools=c.tools or [],
        constraints=c.constraints or [], variables=c.variables or {},
        metadata=c.metadata_ or {},
        created_at=c.created_at, updated_at=c.updated_at,
        prompt_variant_count=len(c.prompt_variants),
        scenario_count=len(c.scenarios),
        persona_count=len(c.personas),
    )


@router.put("/{config_id}", response_model=AgentConfigResponse)
def update_config(config_id: int, body: AgentConfigUpdate, db: Session = Depends(get_db)):
    c = _get_config_or_404(db, config_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "tools" and value is not None:
            value = [t if isinstance(t, dict) else t.model_dump() for t in value]
        if field == "metadata":
            setattr(c, "metadata_", value)
        else:
            setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return AgentConfigResponse(
        id=c.id, name=c.name, description=c.description,
        system_prompt=c.system_prompt, tools=c.tools or [],
        constraints=c.constraints or [], variables=c.variables or {},
        metadata=c.metadata_ or {},
        created_at=c.created_at, updated_at=c.updated_at,
        prompt_variant_count=len(c.prompt_variants),
        scenario_count=len(c.scenarios),
        persona_count=len(c.personas),
    )


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: int, db: Session = Depends(get_db)):
    c = _get_config_or_404(db, config_id)
    db.delete(c)
    db.commit()


# ── AI Enhance endpoints ─────────────────────────────────────────────

class EnhanceRequest(BaseModel):
    text: str
    context: Optional[str] = None


class EnhanceResponse(BaseModel):
    result: str


class SuggestToolsRequest(BaseModel):
    agent_name: str
    description: str
    system_prompt: str
    existing_tools: list[dict] = []


@router.post("/enhance/prompt", response_model=EnhanceResponse)
async def enhance_prompt(body: EnhanceRequest, db: Session = Depends(get_db)):
    """Use LLM to improve a system prompt."""
    from app.services.llm_factory import get_llm
    llm = get_llm(db, temperature=0.4)
    prompt = f"""You are an expert prompt engineer. Improve the following system prompt to be clearer, more structured, and more effective. Keep the same intent but enhance clarity, add helpful structure (numbered steps, clear sections), and ensure it guides the AI model well.

ORIGINAL PROMPT:
---
{body.text}
---

{f"ADDITIONAL CONTEXT: {body.context}" if body.context else ""}

Return ONLY the improved prompt text, nothing else. No explanations, no markdown fences."""
    response = await llm.ainvoke(prompt)
    return EnhanceResponse(result=response.content.strip())


@router.post("/enhance/description", response_model=EnhanceResponse)
async def enhance_description(body: EnhanceRequest, db: Session = Depends(get_db)):
    """Use LLM to improve an agent description."""
    from app.services.llm_factory import get_llm
    llm = get_llm(db, temperature=0.4)
    prompt = f"""Write a clear, concise description for an AI agent based on the following draft. The description should explain what the agent does, who it serves, and its key capabilities in 2-3 sentences.

DRAFT:
---
{body.text}
---

{f"SYSTEM PROMPT FOR CONTEXT: {body.context[:500]}" if body.context else ""}

Return ONLY the improved description text, nothing else."""
    response = await llm.ainvoke(prompt)
    return EnhanceResponse(result=response.content.strip())


@router.post("/enhance/suggest-tools")
async def suggest_tools(body: SuggestToolsRequest, db: Session = Depends(get_db)):
    """Use LLM to suggest tools for the agent."""
    import json
    from app.services.llm_factory import get_llm
    llm = get_llm(db, temperature=0.5)
    existing_names = [t.get("name", "") for t in body.existing_tools]
    prompt = f"""You are an expert in designing AI agent tool sets. Based on the following agent definition, suggest 3-5 tools that this agent should have access to.

AGENT: {body.agent_name}
DESCRIPTION: {body.description}
SYSTEM PROMPT: {body.system_prompt[:800]}
EXISTING TOOLS: {json.dumps(existing_names) if existing_names else "None"}

For each tool, provide:
- name: a snake_case function name
- description: what the tool does (1 sentence)
- parameters: a JSON Schema object describing the parameters

Do NOT suggest tools that already exist. Return a JSON array of tool objects.
Return ONLY valid JSON, no markdown fences."""
    response = await llm.ainvoke(prompt)
    text = response.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    tools = json.loads(text)
    return {"tools": tools}


# ══════════════════════════════════════════════════════════════════════
#  PROMPT VARIANTS
# ══════════════════════════════════════════════════════════════════════

@router.get("/{config_id}/variants", response_model=list[PromptVariantResponse])
def list_variants(config_id: int, db: Session = Depends(get_db)):
    _get_config_or_404(db, config_id)
    return db.query(PromptVariant).filter(
        PromptVariant.agent_config_id == config_id
    ).order_by(PromptVariant.created_at).all()


@router.post("/{config_id}/variants", response_model=PromptVariantResponse, status_code=201)
def create_variant(config_id: int, body: PromptVariantCreate, db: Session = Depends(get_db)):
    _get_config_or_404(db, config_id)
    v = PromptVariant(agent_config_id=config_id, **body.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.delete("/{config_id}/variants/{variant_id}", status_code=204)
def delete_variant(config_id: int, variant_id: int, db: Session = Depends(get_db)):
    v = db.query(PromptVariant).filter(
        PromptVariant.id == variant_id,
        PromptVariant.agent_config_id == config_id,
    ).first()
    if not v:
        raise HTTPException(404, "Variant not found")
    db.delete(v)
    db.commit()


@router.post("/{config_id}/variants/generate", response_model=list[PromptVariantResponse])
async def generate_variants(config_id: int, body: GenerateVariantsRequest, db: Session = Depends(get_db)):
    """Use LLM to generate prompt variations."""
    config = _get_config_or_404(db, config_id)
    from app.services.agent_generators import generate_prompt_variants
    variants = await generate_prompt_variants(db, config, body.count, body.focus)
    return variants


# ══════════════════════════════════════════════════════════════════════
#  SCENARIOS
# ══════════════════════════════════════════════════════════════════════

VALID_SCENARIO_TYPES = {"tool_use", "decision_path", "response_quality", "guardrail"}


@router.get("/{config_id}/scenarios", response_model=list[ScenarioResponse])
def list_scenarios(config_id: int, scenario_type: str | None = None, db: Session = Depends(get_db)):
    _get_config_or_404(db, config_id)
    q = db.query(Scenario).filter(Scenario.agent_config_id == config_id)
    if scenario_type:
        q = q.filter(Scenario.scenario_type == scenario_type)
    return q.order_by(Scenario.created_at).all()


@router.post("/{config_id}/scenarios", response_model=ScenarioResponse, status_code=201)
def create_scenario(config_id: int, body: ScenarioCreate, db: Session = Depends(get_db)):
    _get_config_or_404(db, config_id)
    if body.scenario_type not in VALID_SCENARIO_TYPES:
        raise HTTPException(400, f"Invalid scenario type. Valid: {VALID_SCENARIO_TYPES}")
    s = Scenario(agent_config_id=config_id, **body.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.post("/{config_id}/scenarios/bulk", response_model=list[ScenarioResponse], status_code=201)
def create_scenarios_bulk(config_id: int, body: list[ScenarioCreate], db: Session = Depends(get_db)):
    _get_config_or_404(db, config_id)
    scenarios = []
    for item in body:
        if item.scenario_type not in VALID_SCENARIO_TYPES:
            raise HTTPException(400, f"Invalid scenario type: {item.scenario_type}")
        s = Scenario(agent_config_id=config_id, **item.model_dump())
        db.add(s)
        scenarios.append(s)
    db.commit()
    for s in scenarios:
        db.refresh(s)
    return scenarios


@router.put("/{config_id}/scenarios/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(config_id: int, scenario_id: int, body: ScenarioUpdate, db: Session = Depends(get_db)):
    s = db.query(Scenario).filter(Scenario.id == scenario_id, Scenario.agent_config_id == config_id).first()
    if not s:
        raise HTTPException(404, "Scenario not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{config_id}/scenarios/{scenario_id}", status_code=204)
def delete_scenario(config_id: int, scenario_id: int, db: Session = Depends(get_db)):
    s = db.query(Scenario).filter(Scenario.id == scenario_id, Scenario.agent_config_id == config_id).first()
    if not s:
        raise HTTPException(404, "Scenario not found")
    db.delete(s)
    db.commit()


@router.post("/{config_id}/scenarios/generate", response_model=list[ScenarioResponse])
async def generate_scenarios(config_id: int, body: GenerateScenariosRequest, db: Session = Depends(get_db)):
    """Use LLM to generate test scenarios."""
    config = _get_config_or_404(db, config_id)
    if body.scenario_type not in VALID_SCENARIO_TYPES:
        raise HTTPException(400, f"Invalid scenario type. Valid: {VALID_SCENARIO_TYPES}")
    from app.services.agent_generators import generate_scenarios
    return await generate_scenarios(db, config, body.scenario_type, body.count)


# ══════════════════════════════════════════════════════════════════════
#  PERSONAS
# ══════════════════════════════════════════════════════════════════════

@router.get("/{config_id}/personas", response_model=list[PersonaResponse])
def list_personas(config_id: int, group_name: str | None = None, db: Session = Depends(get_db)):
    _get_config_or_404(db, config_id)
    q = db.query(Persona).filter(Persona.agent_config_id == config_id)
    if group_name:
        q = q.filter(Persona.group_name == group_name)
    return q.order_by(Persona.created_at).all()


@router.post("/{config_id}/personas", response_model=PersonaResponse, status_code=201)
def create_persona(config_id: int, body: PersonaCreate, db: Session = Depends(get_db)):
    _get_config_or_404(db, config_id)
    p = Persona(agent_config_id=config_id, **body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.post("/{config_id}/personas/bulk", response_model=list[PersonaResponse], status_code=201)
def create_personas_bulk(config_id: int, body: list[PersonaCreate], db: Session = Depends(get_db)):
    _get_config_or_404(db, config_id)
    personas = []
    for item in body:
        p = Persona(agent_config_id=config_id, **item.model_dump())
        db.add(p)
        personas.append(p)
    db.commit()
    for p in personas:
        db.refresh(p)
    return personas


@router.put("/{config_id}/personas/{persona_id}", response_model=PersonaResponse)
def update_persona(config_id: int, persona_id: int, body: PersonaUpdate, db: Session = Depends(get_db)):
    p = db.query(Persona).filter(Persona.id == persona_id, Persona.agent_config_id == config_id).first()
    if not p:
        raise HTTPException(404, "Persona not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{config_id}/personas/{persona_id}", status_code=204)
def delete_persona(config_id: int, persona_id: int, db: Session = Depends(get_db)):
    p = db.query(Persona).filter(Persona.id == persona_id, Persona.agent_config_id == config_id).first()
    if not p:
        raise HTTPException(404, "Persona not found")
    db.delete(p)
    db.commit()


@router.post("/{config_id}/personas/generate", response_model=list[PersonaResponse])
async def generate_personas(config_id: int, body: GeneratePersonasRequest, db: Session = Depends(get_db)):
    """Use LLM to generate synthetic personas."""
    config = _get_config_or_404(db, config_id)
    from app.services.agent_generators import generate_personas
    return await generate_personas(db, config, body.audience_description, body.count, body.interaction_count)


@router.get("/{config_id}/personas/templates")
def get_persona_templates():
    """Return pre-built persona archetypes."""
    return [
        {"name": "Tech-savvy Developer", "role": "Software Developer", "expertise_level": "expert",
         "communication_style": "technical", "behavioral_traits": ["detail-oriented", "impatient with vague answers"],
         "goals": ["Get precise technical answers quickly"]},
        {"name": "Non-technical Manager", "role": "Project Manager", "expertise_level": "novice",
         "communication_style": "formal", "behavioral_traits": ["needs simple explanations", "big-picture thinker"],
         "goals": ["Understand outcomes without technical jargon"]},
        {"name": "Frustrated Customer", "role": "End User", "expertise_level": "intermediate",
         "communication_style": "casual", "behavioral_traits": ["impatient", "frustrated", "short messages"],
         "goals": ["Resolve issue as fast as possible"]},
        {"name": "New User Exploring", "role": "First-time User", "expertise_level": "novice",
         "communication_style": "casual", "behavioral_traits": ["curious", "patient", "asks many questions"],
         "goals": ["Learn how the system works"]},
        {"name": "Power User", "role": "Advanced User", "expertise_level": "expert",
         "communication_style": "terse", "behavioral_traits": ["efficient", "knows shortcuts", "expects advanced features"],
         "goals": ["Accomplish complex tasks efficiently"]},
        {"name": "Adversarial Tester", "role": "QA Tester", "expertise_level": "expert",
         "communication_style": "technical", "behavioral_traits": ["tries to break the system", "edge cases", "prompt injection attempts"],
         "goals": ["Find vulnerabilities and unexpected behaviors"]},
    ]
