"""LLM-powered grid search proposer that analyzes documents and suggests hyperparameter combinations."""

import json
from typing import Dict, Any, Optional

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.services.llm_factory import get_llm


SYSTEM_PROMPT = """You are an expert in RAG (Retrieval-Augmented Generation) optimization.
Given information about a document corpus, propose optimal hyperparameter ranges for a grid search.

Consider:
- Document length and complexity → affects chunk_size
- Topic diversity → affects chunk_overlap
- Content density → affects top_k
- Structure (tables, lists, prose) → affects search_type

Return a JSON object with these fields:
- chunk_sizes: array of integers (token counts, e.g. [256, 512, 1024])
- chunk_overlaps: array of integers (percentages, e.g. [10, 20])
- embedding_models: array of strings
- top_k_values: array of integers (e.g. [3, 5, 10])
- search_types: array of strings from ["vector", "hybrid", "mmr"]
- reasoning: string explaining your recommendations"""

USER_PROMPT_TEMPLATE = """Analyze this document corpus and propose a grid search configuration:

Number of documents: {num_docs}
Total content length: ~{total_length} characters
Sample content (first 2000 chars):
{sample_content}

Number of evaluation Q&A pairs: {num_qa_pairs}

Propose hyperparameter ranges optimized for this specific corpus.
Return ONLY valid JSON."""


async def propose_grid_search(
    documents: list[Document],
    num_qa_pairs: int,
    db: Session,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze documents and propose a grid search configuration."""
    llm = get_llm(db, provider_id=provider_id, model=model, temperature=0.2)

    total_length = sum(len(doc.page_content) for doc in documents)
    sample_content = "\n".join(doc.page_content[:500] for doc in documents[:4])

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=USER_PROMPT_TEMPLATE.format(
                num_docs=len(documents),
                total_length=total_length,
                sample_content=sample_content[:2000],
                num_qa_pairs=num_qa_pairs,
            )
        ),
    ]

    response = await llm.ainvoke(messages)
    content = response.content.strip()

    # Parse JSON
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()

    try:
        config = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            config = json.loads(content[start:end])
        else:
            raise ValueError("Failed to parse LLM grid search proposal")

    return config
