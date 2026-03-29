"""RAPTOR — Recursive Abstractive Processing for Tree-Organized Retrieval.

Builds a hierarchical tree of summaries from document chunks, enabling
retrieval at multiple abstraction levels.

Reference: https://arxiv.org/abs/2401.18059
"""

import logging
import numpy as np
from typing import List, Optional

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from app.services.token_tracker import log_llm_response

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """Summarize the following group of text passages into a single coherent paragraph.
Capture the key themes, facts, and relationships. Be concise but comprehensive.

Passages:
{passages}

Summary:"""


def _cluster_chunks(
    chunks: List[Document],
    embeddings,
    n_clusters: int,
    method: str = "kmeans",
) -> List[List[Document]]:
    """Cluster document chunks by embedding similarity.

    Args:
        chunks: Documents to cluster.
        embeddings: Embedding model for vectorizing chunks.
        n_clusters: Target number of clusters.
        method: "kmeans" or "gmm".

    Returns:
        List of document groups (one per cluster).
    """
    if len(chunks) <= n_clusters:
        return [[c] for c in chunks]

    texts = [c.page_content for c in chunks]
    vectors = embeddings.embed_documents(texts)
    X = np.array(vectors)

    if method == "gmm":
        try:
            from sklearn.mixture import GaussianMixture
            gmm = GaussianMixture(n_components=n_clusters, random_state=42)
            labels = gmm.fit_predict(X)
        except ImportError:
            logger.warning("sklearn not available for GMM, falling back to kmeans")
            method = "kmeans"

    if method == "kmeans":
        try:
            from sklearn.cluster import KMeans
            km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = km.fit_predict(X)
        except ImportError:
            # Fallback: simple round-robin grouping
            logger.warning("sklearn not available, using round-robin grouping")
            labels = [i % n_clusters for i in range(len(chunks))]

    # Group chunks by cluster label
    clusters: dict[int, List[Document]] = {}
    for doc, label in zip(chunks, labels):
        clusters.setdefault(int(label), []).append(doc)

    return list(clusters.values())


async def _summarize_cluster(
    cluster: List[Document],
    llm,
    level: int,
    db: Optional[Session],
    provider_name: str,
    model_name: str,
    experiment_id: Optional[int],
    combination_id: Optional[int],
) -> Document:
    """Generate a summary document for a cluster of chunks."""
    passages = "\n---\n".join(d.page_content[:1000] for d in cluster)
    prompt = SUMMARIZE_PROMPT.format(passages=passages)
    response = await llm.ainvoke(prompt)

    if db:
        try:
            log_llm_response(
                db=db, response=response, operation="rag_pipeline",
                provider_name=provider_name, model_name=model_name,
                experiment_id=experiment_id, combination_id=combination_id,
                metadata={"sub_operation": "raptor_summarization", "level": level},
            )
        except Exception:
            pass

    return Document(
        page_content=response.content.strip(),
        metadata={"raptor_level": level, "source_count": len(cluster)},
    )


async def build_raptor_tree(
    chunks: List[Document],
    embeddings,
    llm,
    max_levels: int = 3,
    clustering: str = "kmeans",
    db: Optional[Session] = None,
    provider_name: str = "unknown",
    model_name: str = "unknown",
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[Document]:
    """Build a RAPTOR hierarchical summary tree.

    1. Level 0: original chunks (tagged with raptor_level=0)
    2. Each subsequent level: cluster previous level → summarize clusters
    3. Repeat until max_levels or only 1 cluster remains

    Returns:
        All documents across all levels (original chunks + summaries).
    """
    # Tag original chunks as level 0
    for chunk in chunks:
        chunk.metadata["raptor_level"] = 0

    all_docs = list(chunks)
    current_level_docs = chunks

    log_kwargs = dict(
        db=db, provider_name=provider_name, model_name=model_name,
        experiment_id=experiment_id, combination_id=combination_id,
    )

    for level in range(1, max_levels + 1):
        if len(current_level_docs) <= 1:
            break

        # Target ~sqrt(n) clusters per level (balances depth vs breadth)
        n_clusters = max(2, int(len(current_level_docs) ** 0.5))
        n_clusters = min(n_clusters, len(current_level_docs) // 2)

        logger.info(f"RAPTOR level {level}: clustering {len(current_level_docs)} docs into {n_clusters} clusters")

        clusters = _cluster_chunks(current_level_docs, embeddings, n_clusters, method=clustering)

        # Summarize each cluster
        level_summaries = []
        for cluster in clusters:
            summary = await _summarize_cluster(cluster, llm, level, **log_kwargs)
            level_summaries.append(summary)

        all_docs.extend(level_summaries)
        current_level_docs = level_summaries

        logger.info(f"RAPTOR level {level}: generated {len(level_summaries)} summaries")

    logger.info(f"RAPTOR tree complete: {len(all_docs)} total docs across {level} levels")
    return all_docs


def raptor_retrieve(
    question: str,
    backend,
    top_k: int,
    retrieval_mode: str = "collapsed",
    max_levels: int = 3,
) -> List[Document]:
    """Retrieve from a RAPTOR-indexed collection.

    Modes:
    - collapsed: search all levels together (simple, effective default)
    - tree_traversal: start from top, descend into relevant branches
    - level_specific: bias towards higher levels for broad questions

    Args:
        retrieval_mode: One of "collapsed", "tree_traversal", "level_specific".
    """
    if retrieval_mode == "collapsed":
        # Search across all levels — the vectorstore contains everything
        return backend.similarity_search(question, k=top_k)

    elif retrieval_mode == "tree_traversal":
        # Start from highest level, get top results, then search lower levels
        # with context from higher-level matches
        top_docs = backend.similarity_search(question, k=max(2, top_k // 2))

        # Get context from top-level matches to refine search
        if top_docs:
            context_query = f"{question} {top_docs[0].page_content[:200]}"
            lower_docs = backend.similarity_search(context_query, k=top_k)
            # Merge and deduplicate
            seen = set()
            merged = []
            for doc in top_docs + lower_docs:
                key = doc.page_content[:200]
                if key not in seen:
                    seen.add(key)
                    merged.append(doc)
            return merged[:top_k]

        return top_docs

    elif retrieval_mode == "level_specific":
        # Retrieve more results and prefer higher-level summaries
        candidates = backend.similarity_search(question, k=top_k * 3)

        # Sort by raptor_level (higher first) then by position in results
        candidates.sort(
            key=lambda d: (-d.metadata.get("raptor_level", 0)),
        )
        return candidates[:top_k]

    # Default: collapsed
    return backend.similarity_search(question, k=top_k)
