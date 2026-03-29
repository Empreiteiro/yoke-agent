"""Corrective RAG (CRAG) and Self-RAG retrieval strategies.

CRAG: evaluates retrieval relevance and reformulates queries when docs are irrelevant.
Self-RAG: decides whether retrieval is needed and validates answer grounding.

References:
- CRAG: https://arxiv.org/abs/2401.15884
- Self-RAG: https://arxiv.org/abs/2310.11511
"""

import json
import logging
from typing import List, Optional

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from app.services.token_tracker import log_llm_response

logger = logging.getLogger(__name__)

# --- Prompts ---

RELEVANCE_GRADING_PROMPT = """You are a relevance grader. Given a question and a set of retrieved documents, evaluate whether the documents are relevant to answering the question.

Question: {question}

Documents:
{documents}

Rate the overall relevance as a score from 0.0 to 1.0 where:
- 0.0-0.3 = irrelevant (documents don't contain useful information)
- 0.3-0.7 = partially relevant (some useful information but incomplete)
- 0.7-1.0 = highly relevant (documents contain the information needed)

Respond with ONLY a JSON object: {{"score": <float>, "reasoning": "<brief explanation>"}}"""

QUERY_REFORMULATION_PROMPT = """The following search query did not retrieve relevant results. Reformulate it to improve retrieval.

Original question: {question}
Previous query: {query}
Feedback: {feedback}

Return ONLY the reformulated query, nothing else."""

RETRIEVAL_DECISION_PROMPT = """You are deciding whether to retrieve external documents to answer a question, or if you can answer from general knowledge.

Question: {question}

Consider:
- Does this question require specific facts, data, or details from documents?
- Is this a general knowledge question you can answer confidently?

Respond with ONLY a JSON object: {{"needs_retrieval": true/false, "confidence": <float 0-1>, "reasoning": "<brief>"}}"""

GROUNDING_CHECK_PROMPT = """Check if the following answer is grounded in (supported by) the provided context.

Context:
{context}

Answer: {answer}

Respond with ONLY a JSON object: {{"grounded": true/false, "score": <float 0-1>, "reasoning": "<brief>"}}"""


def _parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response, handling common formatting issues."""
    text = text.strip()
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {}


async def _grade_relevance(
    question: str, docs: List[Document], llm, db, provider_name, model_name,
    experiment_id, combination_id,
) -> float:
    """Grade how relevant retrieved documents are to the question. Returns 0.0-1.0."""
    doc_text = "\n---\n".join(d.page_content[:500] for d in docs[:5])
    prompt = RELEVANCE_GRADING_PROMPT.format(question=question, documents=doc_text)
    response = await llm.ainvoke(prompt)

    if db:
        try:
            log_llm_response(
                db=db, response=response, operation="rag_pipeline",
                provider_name=provider_name, model_name=model_name,
                experiment_id=experiment_id, combination_id=combination_id,
                metadata={"sub_operation": "crag_grading"},
            )
        except Exception:
            pass

    parsed = _parse_json_response(response.content)
    return float(parsed.get("score", 0.5))


async def _reformulate_query(
    question: str, query: str, feedback: str, llm, db, provider_name, model_name,
    experiment_id, combination_id,
) -> str:
    """Reformulate a query for better retrieval."""
    prompt = QUERY_REFORMULATION_PROMPT.format(question=question, query=query, feedback=feedback)
    response = await llm.ainvoke(prompt)

    if db:
        try:
            log_llm_response(
                db=db, response=response, operation="rag_pipeline",
                provider_name=provider_name, model_name=model_name,
                experiment_id=experiment_id, combination_id=combination_id,
                metadata={"sub_operation": "crag_reformulation"},
            )
        except Exception:
            pass

    return response.content.strip().strip('"')


async def crag_retrieve(
    question: str,
    backend,
    llm,
    top_k: int,
    relevance_threshold: float = 0.7,
    max_retries: int = 2,
    db: Optional[Session] = None,
    provider_name: str = "unknown",
    model_name: str = "unknown",
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[Document]:
    """Corrective RAG: retrieve, grade, reformulate if needed.

    1. Retrieve documents
    2. LLM grades relevance
    3. If below threshold: reformulate query and re-retrieve (up to max_retries)
    4. Return final set of documents

    Args:
        relevance_threshold: Score threshold (0-1) for docs to be considered relevant.
        max_retries: Max query reformulation attempts.
    """
    log_kwargs = dict(
        db=db, provider_name=provider_name, model_name=model_name,
        experiment_id=experiment_id, combination_id=combination_id,
    )

    current_query = question
    best_docs = []
    best_score = 0.0

    for attempt in range(1 + max_retries):
        docs = backend.similarity_search(current_query, k=top_k)

        if not docs:
            logger.info(f"CRAG attempt {attempt + 1}: no docs retrieved")
            break

        score = await _grade_relevance(question, docs, llm, **log_kwargs)
        logger.info(f"CRAG attempt {attempt + 1}: relevance={score:.2f} (threshold={relevance_threshold})")

        if score > best_score:
            best_docs = docs
            best_score = score

        if score >= relevance_threshold:
            return docs  # Docs are relevant enough

        # Reformulate for next attempt
        if attempt < max_retries:
            feedback = f"Relevance score was {score:.2f}, below threshold {relevance_threshold}. Documents were not sufficiently relevant."
            current_query = await _reformulate_query(
                question, current_query, feedback, llm, **log_kwargs,
            )
            logger.info(f"CRAG: reformulated query to: {current_query[:100]}")

    # Return best docs found across all attempts
    return best_docs


async def self_rag_retrieve(
    question: str,
    backend,
    llm,
    top_k: int,
    retrieval_threshold: float = 0.5,
    db: Optional[Session] = None,
    provider_name: str = "unknown",
    model_name: str = "unknown",
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[Document]:
    """Self-RAG: LLM decides whether retrieval is needed, then validates grounding.

    1. LLM decides: does this question need retrieval?
    2. If no: return empty docs (pipeline will generate from parametric knowledge)
    3. If yes: retrieve → grade relevance → return docs
    4. After answer generation (handled by pipeline), grounding check can be added

    Args:
        retrieval_threshold: Confidence threshold below which retrieval is triggered.
    """
    log_kwargs = dict(
        db=db, provider_name=provider_name, model_name=model_name,
        experiment_id=experiment_id, combination_id=combination_id,
    )

    # Step 1: Decide whether to retrieve
    prompt = RETRIEVAL_DECISION_PROMPT.format(question=question)
    response = await llm.ainvoke(prompt)

    if db:
        try:
            log_llm_response(
                db=db, response=response, operation="rag_pipeline",
                provider_name=provider_name, model_name=model_name,
                experiment_id=experiment_id, combination_id=combination_id,
                metadata={"sub_operation": "self_rag_decision"},
            )
        except Exception:
            pass

    parsed = _parse_json_response(response.content)
    needs_retrieval = parsed.get("needs_retrieval", True)
    confidence = float(parsed.get("confidence", 0.0))

    logger.info(f"Self-RAG decision: needs_retrieval={needs_retrieval}, confidence={confidence:.2f}")

    # If confident enough to skip retrieval, return minimal context
    if not needs_retrieval and confidence >= retrieval_threshold:
        logger.info("Self-RAG: skipping retrieval (high confidence in parametric knowledge)")
        return []

    # Step 2: Retrieve and grade
    docs = backend.similarity_search(question, k=top_k)

    if docs:
        score = await _grade_relevance(question, docs, llm, **log_kwargs)
        logger.info(f"Self-RAG: retrieval relevance={score:.2f}")

        # If docs are poor, try MMR for diversity
        if score < 0.4:
            logger.info("Self-RAG: low relevance, trying MMR for diversity")
            mmr_docs = backend.mmr_search(question, k=top_k)
            mmr_score = await _grade_relevance(question, mmr_docs, llm, **log_kwargs)
            if mmr_score > score:
                docs = mmr_docs

    return docs
