"""LLM-powered evaluation dataset generation from documents."""

import json
from typing import List, Dict, Optional

from langchain.schema import Document, HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.services.llm_factory import get_llm, _resolve_provider
from app.services.token_tracker import log_llm_response


SYSTEM_PROMPT = """You are an expert at creating evaluation datasets for RAG (Retrieval-Augmented Generation) systems.

Given a set of document chunks, generate question-answer pairs that:
1. Test different aspects of the content (factual recall, reasoning, synthesis)
2. Have clear, unambiguous answers grounded in the provided context
3. Vary in difficulty from simple lookup to multi-hop reasoning
4. Cover the key topics and concepts in the documents

For each Q&A pair, provide:
- question: A clear question about the content
- ground_truth: The expected correct answer
- context: The relevant passage(s) from the document that contain the answer

Return a JSON array of objects with these fields."""

USER_PROMPT_TEMPLATE = """Based on the following document content, generate {num_questions} diverse question-answer pairs for evaluating a RAG system.

Document content:
{content}

Return ONLY a valid JSON array. Each object must have "question", "ground_truth", and "context" fields."""


async def generate_qa_pairs(
    documents: List[Document],
    db: Session,
    num_questions: int = 10,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Generate Q&A evaluation pairs from documents using an LLM."""
    llm = get_llm(db, provider_id=provider_id, model=model, temperature=0.3)

    # Combine document content (truncate if too long)
    combined_content = "\n\n---\n\n".join(
        doc.page_content[:2000] for doc in documents[:10]
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=USER_PROMPT_TEMPLATE.format(
                num_questions=num_questions,
                content=combined_content[:8000],
            )
        ),
    ]

    response = await llm.ainvoke(messages)

    # Log token usage for dataset generation
    try:
        provider = _resolve_provider(db, provider_id, capability="llm")
        log_llm_response(
            db=db,
            response=response,
            operation="dataset_generation",
            provider_name=provider.name,
            model_name=model or provider.default_llm_model or "unknown",
            metadata={"num_questions_requested": num_questions, "num_documents": len(documents)},
        )
    except Exception:
        pass  # Don't fail generation on logging errors

    content = response.content.strip()

    # Parse JSON from response (handle markdown code blocks)
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip()

    try:
        pairs = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON array from the response
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            pairs = json.loads(content[start:end])
        else:
            raise ValueError("Failed to parse LLM response as JSON")

    return pairs
