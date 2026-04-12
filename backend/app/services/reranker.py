"""Post-retrieval rerankers (issue #116).

Two backends are supported and selected via the ``reranker`` hyperparameter:

- ``cohere``: uses the Cohere Rerank API (``rerank-english-v3.0`` by default).
- ``cross_encoder``: uses a local sentence-transformers cross-encoder
  (``cross-encoder/ms-marco-MiniLM-L-6-v2`` by default).

Each reranker consumes a question + a list of candidate documents and returns
at most ``top_n`` documents ordered by the reranker's relevance score. Rerankers
are purely optional — when the parameter is missing or set to ``"none"`` the
caller skips reranking entirely.

Import errors for the optional Cohere / sentence-transformers packages are
caught at call time so the studio still boots even when those dependencies
are not installed. If the provider cannot be loaded the call falls back to
the original ordering.
"""

import logging
import os
from typing import List, Optional, TYPE_CHECKING

from langchain_core.documents import Document

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


DEFAULT_COHERE_MODEL = "rerank-english-v3.0"
DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


# ── Model cache ─────────────────────────────────────────────────────────
# Cross-encoder weights are relatively expensive to load; cache one instance
# per model name across calls inside the worker process.

_cross_encoder_cache: dict = {}


def _get_cross_encoder(model_name: str):
    cached = _cross_encoder_cache.get(model_name)
    if cached is not None:
        return cached
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "sentence-transformers is required for cross-encoder reranking. "
            "Install it with `pip install sentence-transformers`."
        ) from e
    model = CrossEncoder(model_name)
    _cross_encoder_cache[model_name] = model
    return model


def _cohere_client():
    try:
        import cohere  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "cohere is required for Cohere reranking. Install it with `pip install cohere`."
        ) from e
    api_key = os.environ.get("COHERE_API_KEY")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY environment variable is not set.")
    return cohere.Client(api_key)


# ── Public API ──────────────────────────────────────────────────────────


def rerank_documents(
    question: str,
    documents: List[Document],
    reranker: str,
    top_n: int,
    model: Optional[str] = None,
    db: Optional["Session"] = None,
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[Document]:
    """Rerank ``documents`` for ``question`` and return the top ``top_n``.

    ``reranker`` controls the backend — one of ``"cohere"`` or
    ``"cross_encoder"``. Any other value (including ``"none"`` / ``None``)
    short-circuits to the original ordering truncated to ``top_n``.

    When ``db`` is provided, a token-usage log entry is written so reranker
    cost shows up alongside the rest of the combination's usage.
    """
    if not documents:
        return documents
    if not reranker or reranker == "none":
        return documents[:top_n]

    try:
        if reranker == "cohere":
            reranked = _rerank_cohere(
                question=question,
                documents=documents,
                top_n=top_n,
                model=model or DEFAULT_COHERE_MODEL,
            )
        elif reranker in ("cross_encoder", "cross-encoder"):
            reranked = _rerank_cross_encoder(
                question=question,
                documents=documents,
                top_n=top_n,
                model=model or DEFAULT_CROSS_ENCODER_MODEL,
            )
        else:
            logger.warning("Unknown reranker %r — skipping", reranker)
            return documents[:top_n]
    except Exception as e:
        logger.warning("Reranker %s failed (%s) — falling back to raw retrieval order", reranker, e)
        return documents[:top_n]

    # Optional token/cost tracking. Rerankers are billed per search unit
    # (candidate docs) rather than tokens, but we log the request so it shows
    # up in the usage table.
    if db is not None:
        try:
            from app.services.token_tracker import log_token_usage

            log_token_usage(
                db=db,
                operation="reranker",
                provider_name="cohere" if reranker == "cohere" else "local",
                model_name=model or (
                    DEFAULT_COHERE_MODEL if reranker == "cohere" else DEFAULT_CROSS_ENCODER_MODEL
                ),
                model_type="reranker",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                experiment_id=experiment_id,
                combination_id=combination_id,
                metadata={
                    "reranker": reranker,
                    "num_candidates": len(documents),
                    "top_n": top_n,
                },
            )
        except Exception:
            pass  # Never fail the pipeline on logging errors.

    return reranked


# ── Backends ────────────────────────────────────────────────────────────


def _rerank_cohere(
    question: str,
    documents: List[Document],
    top_n: int,
    model: str,
) -> List[Document]:
    client = _cohere_client()
    docs_texts = [d.page_content for d in documents]
    result = client.rerank(
        model=model,
        query=question,
        documents=docs_texts,
        top_n=min(top_n, len(docs_texts)),
    )
    # ``result.results`` is a list of RerankResult with ``index`` and
    # ``relevance_score`` fields; preserve Document metadata by reusing the
    # original instances.
    return [documents[r.index] for r in result.results]


def _rerank_cross_encoder(
    question: str,
    documents: List[Document],
    top_n: int,
    model: str,
) -> List[Document]:
    model_obj = _get_cross_encoder(model)
    pairs = [(question, d.page_content) for d in documents]
    scores = model_obj.predict(pairs)
    scored = sorted(zip(scores, documents), key=lambda x: float(x[0]), reverse=True)
    return [doc for _, doc in scored[: min(top_n, len(scored))]]
