"""Agentic RAG retriever: LLM agent dynamically decides retrieval strategy per question."""

import json
import logging
from typing import List, Dict, Any, Optional

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from app.services.token_tracker import log_llm_response

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """You are a RAG retrieval agent. Your goal is to find the best documents to answer a question.

You have these tools:
- retrieve(query, k): Search for documents using semantic similarity. Returns top-k results.
- retrieve_mmr(query, k): Search using MMR (Maximum Marginal Relevance) for diverse results.
- decompose_question(question): Break a complex question into simpler sub-questions. Returns a list of sub-questions.
- reformulate_query(query, feedback): Rewrite a query to improve retrieval. Provide feedback on why the previous results were insufficient.
- finish(): Stop retrieving and generate the answer with all accumulated context.

Respond with a JSON object (no markdown) with exactly these fields:
- "thought": your reasoning about what to do next
- "action": one of "retrieve", "retrieve_mmr", "decompose_question", "reformulate_query", "finish"
- "args": dict of arguments for the action (empty dict for "finish")

Strategy tips:
- Start with a retrieve call using the original question.
- If results seem irrelevant, try reformulate_query with feedback.
- For multi-part questions, use decompose_question then retrieve for each sub-question.
- Use retrieve_mmr when you need diverse perspectives.
- Call finish when you have enough relevant context (don't over-retrieve).
"""

AGENT_USER_TEMPLATE = """Question: {question}

{history}

What is your next action? Respond with a JSON object."""


def _format_docs_summary(docs: List[Document], max_chars: int = 500) -> str:
    """Create a brief summary of retrieved documents for the agent's context."""
    if not docs:
        return "(no documents found)"
    summaries = []
    for i, doc in enumerate(docs, 1):
        preview = doc.page_content[:max_chars // len(docs)]
        summaries.append(f"[Doc {i}]: {preview}...")
    return "\n".join(summaries)


async def _execute_tool(
    action: str,
    args: Dict[str, Any],
    backend,
    llm,
    top_k: int,
    db: Optional[Session],
    provider_name: str,
    model_name: str,
    experiment_id: Optional[int],
    combination_id: Optional[int],
) -> tuple[List[Document], str]:
    """Execute an agent tool and return (new_docs, observation_text)."""

    if action == "retrieve":
        query = args.get("query", "")
        k = min(args.get("k", top_k), top_k)
        docs = backend.similarity_search(query, k=k)
        return docs, f"Retrieved {len(docs)} docs for: \"{query}\"\n{_format_docs_summary(docs)}"

    elif action == "retrieve_mmr":
        query = args.get("query", "")
        k = min(args.get("k", top_k), top_k)
        docs = backend.mmr_search(query, k=k)
        return docs, f"Retrieved {len(docs)} diverse docs (MMR) for: \"{query}\"\n{_format_docs_summary(docs)}"

    elif action == "decompose_question":
        question = args.get("question", "")
        prompt = f"Break this question into 2-3 simpler sub-questions, one per line:\n{question}"
        response = await llm.ainvoke(prompt)

        if db:
            try:
                log_llm_response(
                    db=db, response=response, operation="rag_pipeline",
                    provider_name=provider_name, model_name=model_name,
                    experiment_id=experiment_id, combination_id=combination_id,
                    metadata={"sub_operation": "agent_decompose"},
                )
            except Exception:
                pass

        sub_questions = [l.strip().lstrip("0123456789.-) ") for l in response.content.strip().split("\n") if l.strip()]
        return [], f"Decomposed into sub-questions:\n" + "\n".join(f"- {q}" for q in sub_questions)

    elif action == "reformulate_query":
        query = args.get("query", "")
        feedback = args.get("feedback", "Results were not relevant enough.")
        prompt = f"Reformulate this search query to get better results.\nOriginal: {query}\nFeedback: {feedback}\nReturn only the new query, nothing else."
        response = await llm.ainvoke(prompt)

        if db:
            try:
                log_llm_response(
                    db=db, response=response, operation="rag_pipeline",
                    provider_name=provider_name, model_name=model_name,
                    experiment_id=experiment_id, combination_id=combination_id,
                    metadata={"sub_operation": "agent_reformulate"},
                )
            except Exception:
                pass

        new_query = response.content.strip().strip('"')
        return [], f"Reformulated query: \"{new_query}\""

    return [], f"Unknown action: {action}"


def _parse_agent_response(text: str) -> Dict[str, Any]:
    """Parse the agent's JSON response, handling common formatting issues."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {"thought": "Failed to parse response", "action": "finish", "args": {}}


async def agentic_retrieve(
    question: str,
    backend,
    llm,
    top_k: int,
    max_steps: int = 5,
    db: Optional[Session] = None,
    provider_name: str = "unknown",
    model_name: str = "unknown",
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[Document]:
    """Run an agentic retrieval loop where the LLM decides the strategy.

    The agent iteratively chooses tools (retrieve, retrieve_mmr, decompose,
    reformulate, evaluate) until it decides it has enough context or max_steps
    is reached.

    Args:
        question: User question to answer.
        backend: VectorStoreBackend instance.
        llm: LangChain LLM instance.
        top_k: Max documents per retrieval call.
        max_steps: Maximum number of agent steps.
        db: Database session for token logging.
        provider_name: Provider name for token logging.
        model_name: Model name for token logging.
        experiment_id: Experiment ID for token logging.
        combination_id: Combination ID for token logging.

    Returns:
        List of accumulated unique documents from all retrieval steps.
    """
    accumulated_docs: Dict[str, Document] = {}  # content_prefix -> Document
    history_lines: List[str] = []

    for step in range(max_steps):
        # Build prompt with history
        history_text = "\n".join(history_lines) if history_lines else "(No actions taken yet)"
        user_msg = AGENT_USER_TEMPLATE.format(question=question, history=history_text)
        full_prompt = f"{AGENT_SYSTEM_PROMPT}\n\n{user_msg}"

        # Ask agent for next action
        response = await llm.ainvoke(full_prompt)

        # Log agent reasoning LLM call
        if db:
            try:
                log_llm_response(
                    db=db, response=response, operation="rag_pipeline",
                    provider_name=provider_name, model_name=model_name,
                    experiment_id=experiment_id, combination_id=combination_id,
                    metadata={"sub_operation": "agent_reasoning", "step": step + 1},
                )
            except Exception:
                pass

        parsed = _parse_agent_response(response.content)
        action = parsed.get("action", "finish")
        args = parsed.get("args", {})
        thought = parsed.get("thought", "")

        logger.info(f"Agent step {step + 1}/{max_steps}: action={action}, thought={thought[:100]}")

        if action == "finish":
            break

        # Execute tool
        new_docs, observation = await _execute_tool(
            action=action,
            args=args,
            backend=backend,
            llm=llm,
            top_k=top_k,
            db=db,
            provider_name=provider_name,
            model_name=model_name,
            experiment_id=experiment_id,
            combination_id=combination_id,
        )

        # Accumulate unique documents
        for doc in new_docs:
            key = doc.page_content[:200]
            if key not in accumulated_docs:
                accumulated_docs[key] = doc

        # Add to history
        history_lines.append(f"Step {step + 1}: [{action}] {observation}")

    result_docs = list(accumulated_docs.values())
    logger.info(f"Agentic retrieval complete: {len(result_docs)} unique docs in {min(step + 1, max_steps)} steps")
    return result_docs[:top_k * 2]  # Allow slightly more docs than top_k since agent curates them
