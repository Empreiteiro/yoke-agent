"""Multi-Query retriever: generate alternative queries and merge results via Reciprocal Rank Fusion."""

import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from app.services.token_tracker import log_llm_response

logger = logging.getLogger(__name__)

QUERY_GENERATION_PROMPT = """You are a helpful assistant that generates alternative search queries.
Given the following question, generate {count} alternative formulations that could help find relevant information.
Each alternative should approach the topic from a different angle or use different vocabulary.

Original question: {question}

Return ONLY the alternative queries, one per line, without numbering or bullets."""


async def generate_alternative_queries(
    question: str,
    llm,
    count: int = 3,
    db: Optional[Session] = None,
    provider_name: str = "unknown",
    model_name: str = "unknown",
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[str]:
    """Generate alternative query formulations using an LLM."""
    prompt = QUERY_GENERATION_PROMPT.format(question=question, count=count)
    response = await llm.ainvoke(prompt)

    # Log token usage for query generation
    if db:
        try:
            log_llm_response(
                db=db,
                response=response,
                operation="rag_pipeline",
                provider_name=provider_name,
                model_name=model_name,
                experiment_id=experiment_id,
                combination_id=combination_id,
                metadata={"sub_operation": "multi_query_generation", "question": question[:100]},
            )
        except Exception:
            pass

    # Parse alternatives (one per line, skip empty lines)
    alternatives = [
        line.strip().lstrip("0123456789.-) ")
        for line in response.content.strip().split("\n")
        if line.strip()
    ]
    return alternatives[:count]


def reciprocal_rank_fusion(
    ranked_lists: List[List[Document]],
    k: int = 60,
) -> List[Document]:
    """Merge multiple ranked document lists using Reciprocal Rank Fusion (RRF).

    RRF score for a document d across all lists:
        score(d) = sum( 1 / (k + rank_i) )
    where rank_i is the 1-based rank of d in list i (only for lists containing d).

    Args:
        ranked_lists: List of ranked document lists (each from a different query).
        k: RRF constant (default 60, standard value from the original paper).

    Returns:
        Documents sorted by fused score (descending).
    """
    scores: Dict[str, float] = defaultdict(float)
    doc_map: Dict[str, Document] = {}

    for doc_list in ranked_lists:
        for rank, doc in enumerate(doc_list, start=1):
            doc_key = doc.page_content[:200]  # Use content prefix as dedup key
            scores[doc_key] += 1.0 / (k + rank)
            if doc_key not in doc_map:
                doc_map[doc_key] = doc

    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [doc_map[key] for key in sorted_keys]


async def multi_query_retrieve(
    question: str,
    backend,
    llm,
    top_k: int,
    multi_query_count: int = 3,
    db: Optional[Session] = None,
    provider_name: str = "unknown",
    model_name: str = "unknown",
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[Document]:
    """Retrieve documents using Multi-Query strategy with RRF fusion.

    1. Generate N alternative queries via LLM
    2. Retrieve top-k docs for original + each alternative
    3. Merge all results via Reciprocal Rank Fusion
    4. Return top-k unique documents

    Args:
        question: Original user question.
        backend: VectorStoreBackend instance.
        llm: LangChain LLM instance.
        top_k: Number of documents to return.
        multi_query_count: Number of alternative queries to generate.
        db: Database session for token logging.
        provider_name: Provider name for token logging.
        model_name: Model name for token logging.
        experiment_id: Experiment ID for token logging.
        combination_id: Combination ID for token logging.

    Returns:
        List of retrieved documents sorted by fused relevance.
    """
    # Generate alternative queries
    alternatives = await generate_alternative_queries(
        question=question,
        llm=llm,
        count=multi_query_count,
        db=db,
        provider_name=provider_name,
        model_name=model_name,
        experiment_id=experiment_id,
        combination_id=combination_id,
    )

    all_queries = [question] + alternatives
    logger.info(f"Multi-query: {len(all_queries)} queries (original + {len(alternatives)} alternatives)")

    # Retrieve docs for each query
    ranked_lists = []
    for q in all_queries:
        docs = backend.similarity_search(q, k=top_k)
        ranked_lists.append(docs)

    # Fuse results via RRF and return top-k
    fused = reciprocal_rank_fusion(ranked_lists)
    return fused[:top_k]
