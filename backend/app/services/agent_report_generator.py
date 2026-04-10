"""
Generates LLM-powered prompt improvement reports based on experiment results.
"""
import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.agent import (
    AgentConfig, AgentExperiment, AgentExperimentCombination,
    PromptVariant, SimulationTranscript, SimulationMetrics,
)
from app.services.llm_factory import get_llm, resolve_provider
from app.services.token_tracker import log_llm_response

logger = logging.getLogger(__name__)


async def generate_report(db: Session, experiment_id: int) -> dict:
    """Generate a comprehensive prompt improvement report."""
    exp = db.query(AgentExperiment).filter(AgentExperiment.id == experiment_id).first()
    if not exp:
        raise ValueError(f"Experiment {experiment_id} not found")

    config = db.query(AgentConfig).filter(AgentConfig.id == exp.agent_config_id).first()
    combos = db.query(AgentExperimentCombination).filter(
        AgentExperimentCombination.experiment_id == experiment_id,
    ).order_by(AgentExperimentCombination.overall_score.desc().nullslast()).all()

    # Gather context for the report
    best_combo = combos[0] if combos else None
    worst_combo = combos[-1] if combos else None

    # Get sample failing transcripts
    failing_transcripts = []
    for combo in combos:
        transcripts = db.query(SimulationTranscript).filter(
            SimulationTranscript.combination_id == combo.id,
        ).all()
        for t in transcripts:
            metrics = db.query(SimulationMetrics).filter(
                SimulationMetrics.transcript_id == t.id,
            ).first()
            if metrics and metrics.metrics:
                avg_score = sum(metrics.metrics.values()) / len(metrics.metrics) if metrics.metrics else 0
                if avg_score < 0.5:
                    failing_transcripts.append({
                        "combo_params": combo.params,
                        "messages": t.messages[:6],  # first 6 messages
                        "metrics": metrics.metrics,
                        "scenario_type": metrics.scenario_type,
                    })
            if len(failing_transcripts) >= 5:
                break
        if len(failing_transcripts) >= 5:
            break

    # Get prompt variants used
    variant_ids = set()
    for c in combos:
        if c.params and c.params.get("prompt_variant_id"):
            variant_ids.add(c.params["prompt_variant_id"])
    variants = db.query(PromptVariant).filter(PromptVariant.id.in_(variant_ids)).all() if variant_ids else []

    # Build metrics summary
    metrics_summary = []
    for c in combos[:10]:
        metrics_summary.append({
            "params": {
                "model": c.params.get("model"),
                "temperature": c.params.get("temperature"),
                "prompt_variant_id": c.params.get("prompt_variant_id"),
            },
            "overall_score": c.overall_score,
            "aggregated_metrics": c.aggregated_metrics,
        })

    llm = get_llm(db, temperature=0.3, isolated=True)

    prompt = f"""You are an expert AI agent evaluation consultant. Analyze these experiment results and provide actionable recommendations for improving the agent's prompt and configuration.

## Agent Configuration
Name: {config.name}
System Prompt (original):
---
{config.system_prompt[:1500]}
---

Constraints: {json.dumps(config.constraints or [])}
Tools: {json.dumps([t.get("name", "") for t in (config.tools or [])])}

## Prompt Variants Tested
{json.dumps([{"id": v.id, "name": v.variant_name, "prompt_preview": v.system_prompt[:200]} for v in variants], indent=2)}

## Results Summary (Top 10 combinations, ranked by score)
{json.dumps(metrics_summary, indent=2)}

## Best Combination
Score: {best_combo.overall_score if best_combo else "N/A"}
Params: {json.dumps(best_combo.params) if best_combo else "N/A"}

## Sample Failing Interactions
{json.dumps(failing_transcripts[:3], indent=2)}

---

Please provide a comprehensive report with:

1. **Executive Summary** (3-5 sentences)
2. **Key Findings**:
   - Which model performed best and why
   - Which prompt variant was most effective
   - Impact of temperature on results
3. **Failure Analysis**: Common failure patterns across failing interactions
4. **Prompt Improvement Suggestions**: Provide 3-5 specific, actionable suggestions with:
   - What to change in the prompt
   - Why it should help
   - Expected impact (high/medium/low)
   - Before/after example text (specific excerpts to change)
5. **Persona-Specific Insights**: Any patterns related to different user types
6. **Recommended Next Steps**: Prioritized action items

Format the report in Markdown."""

    response = await llm.ainvoke(prompt)

    # Log token usage for the report-generation call — these prompts are
    # big (full transcript summaries) and worth tracking per experiment.
    try:
        report_provider = resolve_provider(db, capability="llm")
        log_llm_response(
            db=db,
            response=response,
            operation="agent_report",
            provider_name=report_provider.name,
            model_name=report_provider.default_llm_model or "unknown",
            experiment_id=experiment_id,
            metadata={"sub_operation": "improvement_report"},
            prompt_text=prompt,
        )
    except Exception as log_err:
        logger.debug(f"Failed to log report token usage: {log_err}")

    report_text = response.content if hasattr(response, "content") else str(response)

    # Store the report in the experiment's grid_config
    exp_config = dict(exp.grid_config or {})
    exp_config["report"] = report_text
    exp_config["report_generated"] = True
    exp.grid_config = exp_config
    flag_modified(exp, "grid_config")
    db.commit()

    return {"report": report_text, "experiment_id": experiment_id}
