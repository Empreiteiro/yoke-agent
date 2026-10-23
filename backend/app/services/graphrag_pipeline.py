"""GraphRAG pipeline — knowledge graph construction and retrieval."""

import logging
from typing import List, Dict, Any, Optional

import networkx as nx
import numpy as np
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.orm import Session

from app.services.llm_factory import get_llm, get_embeddings, _resolve_provider
from app.services.rag_pipeline import chunk_documents
from app.services.token_tracker import log_llm_response, log_embedding_usage

logger = logging.getLogger(__name__)


# ─── Entity Extraction ──────────────────────────────────

async def extract_entities_and_relations(
    chunks: List[Document],
    llm,
    max_gleanings: int = 1,
    db: Optional[Session] = None,
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Extract entities and relations from document chunks using LLM.

    Returns list of dicts: [{"entities": [...], "relations": [...], "source_chunk_idx": int}]
    """
    extraction_prompt = """Extract all entities and relationships from the following text.

For each entity, provide:
- name: the entity name (normalized, capitalized)
- type: the entity type (Person, Organization, Concept, Event, Location, etc.)
- description: a brief description based on the text

For each relationship, provide:
- source: source entity name
- target: target entity name
- type: relationship type (e.g., "founded_by", "part_of", "causes", "mentioned_in")
- description: brief description of the relationship

Return valid JSON with two arrays: "entities" and "relations".

Text:
{text}

Return ONLY valid JSON: {{"entities": [...], "relations": [...]}}"""

    all_extractions = []
    provider = _resolve_provider(db, None, capability="llm") if db else None

    for idx, chunk in enumerate(chunks):
        for gleaning in range(max(1, max_gleanings)):
            prompt = extraction_prompt.format(text=chunk.page_content)
            if gleaning > 0:
                prompt += f"\n\nThis is pass {gleaning + 1}. Look for entities and relations you may have missed before."

            try:
                response = await llm.ainvoke(prompt)

                # Log token usage
                if db and provider:
                    try:
                        log_llm_response(
                            db=db,
                            response=response,
                            operation="rag_pipeline",
                            provider_name=provider.name,
                            model_name=provider.default_llm_model or "unknown",
                            experiment_id=experiment_id,
                            combination_id=combination_id,
                            metadata={"step": "entity_extraction", "chunk": idx, "gleaning": gleaning},
                        )
                    except Exception:
                        pass

                # Parse response
                import json
                content = response.content.strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()
                if content.startswith("```"):
                    content = content[3:].strip()

                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        parsed = json.loads(content[start:end])
                    else:
                        parsed = {"entities": [], "relations": []}

                all_extractions.append({
                    "entities": parsed.get("entities", []),
                    "relations": parsed.get("relations", []),
                    "source_chunk_idx": idx,
                })
            except Exception as e:
                logger.warning(f"Entity extraction failed for chunk {idx}, gleaning {gleaning}: {e}")
                all_extractions.append({"entities": [], "relations": [], "source_chunk_idx": idx})

    return all_extractions


# ─── Graph Construction ──────────────────────────────────

def build_networkx_graph(
    extractions: List[Dict[str, Any]],
    chunks: List[Document],
) -> nx.Graph:
    """Build a NetworkX graph from extracted entities and relations."""
    G = nx.Graph()

    for extraction in extractions:
        chunk_idx = extraction["source_chunk_idx"]
        chunk_text = chunks[chunk_idx].page_content if chunk_idx < len(chunks) else ""

        for entity in extraction.get("entities", []):
            name = entity.get("name", "").strip()
            if not name:
                continue
            if G.has_node(name):
                # Merge descriptions
                existing = G.nodes[name]
                existing["chunk_ids"] = list(set(existing.get("chunk_ids", []) + [chunk_idx]))
                if entity.get("description") and entity["description"] not in existing.get("description", ""):
                    existing["description"] = existing.get("description", "") + " | " + entity["description"]
            else:
                G.add_node(name, **{
                    "type": entity.get("type", "Unknown"),
                    "description": entity.get("description", ""),
                    "chunk_ids": [chunk_idx],
                })

        for relation in extraction.get("relations", []):
            source = relation.get("source", "").strip()
            target = relation.get("target", "").strip()
            if not source or not target:
                continue
            # Ensure nodes exist
            if not G.has_node(source):
                G.add_node(source, type="Unknown", description="", chunk_ids=[chunk_idx])
            if not G.has_node(target):
                G.add_node(target, type="Unknown", description="", chunk_ids=[chunk_idx])

            G.add_edge(source, target, **{
                "type": relation.get("type", "related_to"),
                "description": relation.get("description", ""),
                "chunk_ids": [chunk_idx],
            })

    return G


# ─── Community Detection ─────────────────────────────────

def detect_communities(
    graph: nx.Graph,
    community_level: int = 1,
) -> Dict[int, List[str]]:
    """Run community detection on the graph.

    Args:
        graph: NetworkX graph
        community_level: Resolution level (higher = more fine-grained)

    Returns:
        Dict mapping community_id -> list of node names
    """
    if len(graph.nodes) == 0:
        return {}

    try:
        from graspologic.partition import hierarchical_leiden
        community_map = hierarchical_leiden(graph, max_cluster_size=max(10, len(graph.nodes) // 2))
        # Extract communities at the requested level
        communities = {}
        for node_id, community_info in community_map.items():
            level_communities = [c for c in community_info if c.level <= community_level]
            if level_communities:
                comm_id = level_communities[-1].cluster
                communities.setdefault(comm_id, []).append(node_id)
        return communities if communities else {0: list(graph.nodes)}
    except Exception as e:
        logger.warning(f"Leiden community detection failed: {e}. Using connected components.")
        # Fallback: connected components
        communities = {}
        for idx, component in enumerate(nx.connected_components(graph)):
            communities[idx] = list(component)
        return communities if communities else {0: list(graph.nodes)}


# ─── Community Summarization ─────────────────────────────

async def generate_community_summaries(
    graph: nx.Graph,
    communities: Dict[int, List[str]],
    llm,
    db: Optional[Session] = None,
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> Dict[int, str]:
    """Generate natural language summaries for each community."""
    summaries = {}
    provider = _resolve_provider(db, None, capability="llm") if db else None

    for comm_id, nodes in communities.items():
        # Collect entity info
        entity_descriptions = []
        for node in nodes[:20]:  # Limit to prevent prompt overflow
            data = graph.nodes.get(node, {})
            desc = f"- {node} ({data.get('type', 'Unknown')}): {data.get('description', 'No description')}"
            entity_descriptions.append(desc)

        # Collect relation info
        relation_descriptions = []
        for u, v, data in graph.edges(nodes, data=True):
            if u in nodes or v in nodes:
                desc = f"- {u} --[{data.get('type', 'related_to')}]--> {v}: {data.get('description', '')}"
                relation_descriptions.append(desc)
                if len(relation_descriptions) >= 20:
                    break

        prompt = f"""Summarize the following group of related entities and their relationships into a coherent paragraph.

Entities:
{chr(10).join(entity_descriptions)}

Relationships:
{chr(10).join(relation_descriptions)}

Write a concise summary (2-4 sentences) describing what this group represents and how the entities relate to each other."""

        try:
            response = await llm.ainvoke(prompt)
            summaries[comm_id] = response.content.strip()

            if db and provider:
                try:
                    log_llm_response(
                        db=db,
                        response=response,
                        operation="rag_pipeline",
                        provider_name=provider.name,
                        model_name=provider.default_llm_model or "unknown",
                        experiment_id=experiment_id,
                        combination_id=combination_id,
                        metadata={"step": "community_summary", "community_id": comm_id},
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Community summary failed for community {comm_id}: {e}")
            summaries[comm_id] = f"Community with entities: {', '.join(nodes[:5])}"

    return summaries


# ─── Search Functions ─────────────────────────────────────

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


def local_search(
    query_embedding: List[float],
    graph: nx.Graph,
    entity_embeddings: Dict[str, List[float]],
    chunks: List[Document],
    top_k_entities: int = 5,
    n_hops: int = 2,
) -> List[str]:
    """Local search: find matching entities, traverse graph, collect context."""
    if not entity_embeddings:
        return []

    # Find top-k matching entities
    similarities = [
        (name, _cosine_similarity(query_embedding, emb))
        for name, emb in entity_embeddings.items()
    ]
    similarities.sort(key=lambda x: x[1], reverse=True)
    top_entities = [name for name, _ in similarities[:top_k_entities]]

    # Traverse N hops from matched entities
    visited_nodes = set()
    for entity in top_entities:
        if entity in graph:
            # BFS up to n_hops
            visited = {entity}
            frontier = {entity}
            for _ in range(n_hops):
                next_frontier = set()
                for node in frontier:
                    for neighbor in graph.neighbors(node):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            next_frontier.add(neighbor)
                frontier = next_frontier
            visited_nodes.update(visited)

    # Collect chunk content from traversed nodes
    chunk_ids = set()
    for node in visited_nodes:
        node_data = graph.nodes.get(node, {})
        chunk_ids.update(node_data.get("chunk_ids", []))

    contexts = []
    for idx in sorted(chunk_ids):
        if idx < len(chunks):
            contexts.append(chunks[idx].page_content)

    return contexts[:10]  # Limit context size


def global_search(
    query_embedding: List[float],
    community_summaries: Dict[int, str],
    summary_embeddings: Dict[int, List[float]],
    top_k_communities: int = 3,
) -> List[str]:
    """Global search: match query against community summaries."""
    if not summary_embeddings:
        return list(community_summaries.values())[:top_k_communities]

    similarities = [
        (comm_id, _cosine_similarity(query_embedding, emb))
        for comm_id, emb in summary_embeddings.items()
    ]
    similarities.sort(key=lambda x: x[1], reverse=True)
    top_communities = [comm_id for comm_id, _ in similarities[:top_k_communities]]

    return [community_summaries[c] for c in top_communities if c in community_summaries]


# ─── Main Pipeline ────────────────────────────────────────

async def run_graphrag_pipeline(
    documents: List[Document],
    questions: List[str],
    params: Dict[str, Any],
    db: Session,
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Run a GraphRAG pipeline. Same return format as run_rag_pipeline.

    Returns: List[Dict] with 'question', 'answer', 'contexts'
    """
    chunk_size = params["chunk_size"]
    chunk_overlap = params["chunk_overlap"]
    embedding_model = params["embedding_model"]
    embedding_dimensions = params.get("embedding_dimensions")
    chunking_strategy = params.get("chunking_strategy", "recursive")
    entity_extraction_model = params.get("entity_extraction_model", "gpt-6-luna")
    max_gleanings = params.get("max_gleanings", 1)
    community_level = params.get("community_level", 1)
    search_mode = params.get("search_mode", "local")
    answer_language = params.get("answer_language", "auto")

    # 1. Create embeddings
    embeddings = get_embeddings(db, model=embedding_model, dimensions=embedding_dimensions)

    # 2. Chunk documents
    chunks = chunk_documents(documents, chunk_size, chunk_overlap, chunking_strategy, embeddings=embeddings)

    if not chunks:
        return [{"question": q, "answer": "No content to process.", "contexts": []} for q in questions]

    # 3. Create LLM for entity extraction
    extraction_llm = get_llm(db, model=entity_extraction_model, temperature=0)

    # 4. Extract entities and relations
    logger.info(f"GraphRAG: Extracting entities from {len(chunks)} chunks (max_gleanings={max_gleanings})")
    extractions = await extract_entities_and_relations(
        chunks, extraction_llm, max_gleanings,
        db=db, experiment_id=experiment_id, combination_id=combination_id,
    )

    # 5. Build graph
    graph = build_networkx_graph(extractions, chunks)
    logger.info(f"GraphRAG: Graph built with {len(graph.nodes)} nodes, {len(graph.edges)} edges")

    if len(graph.nodes) == 0:
        return [{"question": q, "answer": "No entities extracted from the document.", "contexts": []} for q in questions]

    # 6. Community detection
    communities = detect_communities(graph, community_level)
    logger.info(f"GraphRAG: {len(communities)} communities detected")

    # 7. Generate community summaries
    answer_llm = get_llm(db, temperature=0)
    community_summaries = await generate_community_summaries(
        graph, communities, answer_llm,
        db=db, experiment_id=experiment_id, combination_id=combination_id,
    )

    # 8. Pre-compute embeddings for entities and community summaries
    entity_names = list(graph.nodes)
    entity_texts = [
        f"{name}: {graph.nodes[name].get('description', '')}"
        for name in entity_names
    ]

    entity_embeddings = {}
    summary_embeddings = {}

    try:
        if entity_texts:
            entity_vecs = embeddings.embed_documents(entity_texts)
            entity_embeddings = dict(zip(entity_names, entity_vecs))

            # Log embedding usage
            try:
                log_embedding_usage(
                    db=db,
                    texts=entity_texts,
                    operation="rag_pipeline",
                    provider_name=_resolve_provider(db, None, capability="embedding", model=embedding_model).name,
                    model_name=embedding_model,
                    experiment_id=experiment_id,
                    combination_id=combination_id,
                    metadata={"step": "entity_embedding", "num_entities": len(entity_texts)},
                )
            except Exception:
                pass

        if community_summaries:
            summary_texts = list(community_summaries.values())
            summary_vecs = embeddings.embed_documents(summary_texts)
            summary_embeddings = dict(zip(community_summaries.keys(), summary_vecs))
    except Exception as e:
        logger.warning(f"GraphRAG: Embedding computation failed: {e}")

    # 9. Answer questions
    results = []
    llm_provider = _resolve_provider(db, None, capability="llm")

    for question in questions:
        # Embed query
        query_embedding = embeddings.embed_query(question)

        # Search based on mode
        if search_mode == "global":
            context_texts = global_search(query_embedding, community_summaries, summary_embeddings)
        elif search_mode == "hybrid":
            local_ctx = local_search(query_embedding, graph, entity_embeddings, chunks)
            global_ctx = global_search(query_embedding, community_summaries, summary_embeddings)
            # Combine and deduplicate
            seen = set()
            context_texts = []
            for ctx in local_ctx + global_ctx:
                if ctx not in seen:
                    seen.add(ctx)
                    context_texts.append(ctx)
        else:  # local (default)
            context_texts = local_search(query_embedding, graph, entity_embeddings, chunks)

        combined_context = "\n\n".join(context_texts)

        # Generate answer
        lang_instruction = f"\nAnswer in {answer_language}." if answer_language and answer_language != "auto" else ""
        prompt = f"""Based on the following context, answer the question.
If the answer cannot be found in the context, say "I cannot find the answer in the provided context."{lang_instruction}

Context:
{combined_context}

Question: {question}

Answer:"""

        response = await answer_llm.ainvoke(prompt)

        # Log token usage
        try:
            log_llm_response(
                db=db,
                response=response,
                operation="rag_pipeline",
                provider_name=llm_provider.name,
                model_name=llm_provider.default_llm_model or "unknown",
                experiment_id=experiment_id,
                combination_id=combination_id,
                metadata={"question": question[:100]},
            )
        except Exception:
            pass

        results.append({
            "question": question,
            "answer": response.content,
            "contexts": context_texts,
        })

    return results
