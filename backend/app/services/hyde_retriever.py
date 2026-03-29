"""HyDE (Hypothetical Document Embeddings) retriever.

Generates a hypothetical answer via LLM, embeds it, then uses that
embedding for similarity search — bridging the semantic gap between
short questions and longer document passages.

Reference: https://arxiv.org/abs/2212.10496
"""

import logging
from typing import List, Optional

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from app.services.token_tracker import log_llm_response

logger = logging.getLogger(__name__)

HYDE_PROMPT = """Write a short passage (3-5 sentences) that would answer the following question.
Do not say "I don't know". Write a plausible answer even if you are unsure.

Question: {question}

Passage:"""


async def hyde_retrieve(
    question: str,
    backend,
    llm,
    embeddings,
    top_k: int,
    db: Optional[Session] = None,
    provider_name: str = "unknown",
    model_name: str = "unknown",
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[Document]:
    """Retrieve documents using HyDE strategy.

    1. LLM generates a hypothetical answer to the question
    2. The hypothetical answer is embedded (closer to real docs than the question)
    3. Similarity search uses the hypothetical embedding
    4. Returns top-k documents

    Args:
        question: User question.
        backend: VectorStoreBackend instance.
        llm: LangChain LLM instance.
        embeddings: Embedding model instance (for embedding the hypothesis).
        top_k: Number of documents to return.
        db: Database session for token logging.
    """
    # Generate hypothetical answer
    prompt = HYDE_PROMPT.format(question=question)
    response = await llm.ainvoke(prompt)
    hypothetical_answer = response.content.strip()

    # Log token usage
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
                metadata={"sub_operation": "hyde_generation", "question": question[:100]},
            )
        except Exception:
            pass

    logger.info(f"HyDE: generated hypothesis ({len(hypothetical_answer)} chars) for question: {question[:80]}")

    # Embed the hypothetical answer and search with it
    hypothesis_embedding = embeddings.embed_query(hypothetical_answer)

    # Use the backend's similarity_search_by_vector if available, else fall back
    if hasattr(backend, "similarity_search_by_vector"):
        retrieved_docs = backend.similarity_search_by_vector(hypothesis_embedding, k=top_k)
    else:
        # Fallback: search with the hypothetical text directly
        retrieved_docs = backend.similarity_search(hypothetical_answer, k=top_k)

    return retrieved_docs
