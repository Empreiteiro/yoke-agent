"""RAG pipeline execution with configurable hyperparameters."""

import time
from typing import List, Dict, Any, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter, TokenTextSplitter
from langchain_core.documents import Document
from sqlalchemy.orm import Session

from app.services.llm_factory import get_llm, get_embeddings, _resolve_provider
from app.services.vectorstore_factory import create_vectorstore_backend
from app.services.token_tracker import log_llm_response, log_embedding_usage

DEFAULT_PROMPT_TEMPLATE = """Based on the following context, answer the question.
If the answer cannot be found in the context, say "I cannot find the answer in the provided context."{lang_instruction}

Context:
{context}

Question: {question}

Answer:"""


def _build_prompt(template: str, context: str, question: str, answer_language: str = "auto") -> str:
    """Build the final prompt from a template, injecting context and question."""
    lang_instruction = f"\nAnswer in {answer_language}." if answer_language and answer_language != "auto" else ""
    return template.format(
        context=context,
        question=question,
        lang_instruction=lang_instruction,
    )


def chunk_documents(
    documents: List[Document],
    chunk_size: int,
    chunk_overlap_pct: int,
    chunking_strategy: str = "recursive",
    embeddings=None,
) -> List[Document]:
    """Split documents into chunks with given size, overlap, and strategy.

    Args:
        documents: Source documents to split.
        chunk_size: Size of each chunk.
        chunk_overlap_pct: Overlap as percentage of chunk_size.
        chunking_strategy: One of "recursive", "token", "semantic".
        embeddings: Required for semantic chunking (embedding model instance).
    """
    overlap = int(chunk_size * chunk_overlap_pct / 100)

    if chunking_strategy == "token":
        splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
        )
    elif chunking_strategy == "semantic":
        try:
            from langchain_experimental.text_splitter import SemanticChunker
            if embeddings is None:
                raise ValueError("Embeddings required for semantic chunking")
            splitter = SemanticChunker(
                embeddings,
                breakpoint_threshold_type="percentile",
            )
            # SemanticChunker ignores chunk_size; it groups by semantic similarity
            return splitter.split_documents(documents)
        except ImportError:
            # Fallback to recursive if langchain_experimental not available
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
    else:  # recursive (default)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    return splitter.split_documents(documents)


async def run_rag_pipeline(
    documents: List[Document],
    questions: List[str],
    params: Dict[str, Any],
    db: Session,
    vectorstore_type: str = "chromadb",
    vectorstore_config: Dict[str, Any] | None = None,
    llm_provider_id: Optional[int] = None,
    embedding_provider_id: Optional[int] = None,
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Run a RAG pipeline with the given parameters and return answers for each question.

    Args:
        documents: Source documents to index
        questions: List of questions to answer
        params: RAG hyperparameters (chunk_size, chunk_overlap, embedding_model, top_k, search_type)
        db: Database session for resolving providers
        vectorstore_type: Type of vector store to use
        vectorstore_config: Optional vector store configuration
        llm_provider_id: Provider ID for the LLM (auto-detect if None)
        embedding_provider_id: Provider ID for embeddings (auto-detect if None)

    Returns:
        List of dicts with 'question', 'answer', and 'contexts' for each question
    """
    chunk_size = params["chunk_size"]
    chunk_overlap = params["chunk_overlap"]
    embedding_model = params["embedding_model"]
    top_k = params["top_k"]
    search_type = params["search_type"]
    embedding_dimensions = params.get("embedding_dimensions")
    distance_metric = params.get("distance_metric", "cosine")
    chunking_strategy = params.get("chunking_strategy", "recursive")
    answer_language = params.get("answer_language", "auto")

    # Resolve provider info for token logging
    llm_provider = _resolve_provider(db, llm_provider_id, capability="llm")

    # Resolve prompt template (custom or default)
    prompt_template = params.get("prompt_template") or DEFAULT_PROMPT_TEMPLATE

    # --- CAG: Cache-Augmented Generation (full-context baseline, no retrieval) ---
    if search_type == "cag":
        llm = get_llm(db, provider_id=llm_provider_id, temperature=0)
        full_text = "\n\n".join(doc.page_content for doc in documents)
        # Truncate to ~100K chars to stay within context limits
        full_text = full_text[:100_000]

        results = []
        for question in questions:
            prompt = _build_prompt(prompt_template, full_text, question, answer_language)
            gen_start = time.perf_counter()
            response = await llm.ainvoke(prompt)
            gen_ms = (time.perf_counter() - gen_start) * 1000.0
            try:
                log_llm_response(
                    db=db, response=response, operation="rag_pipeline",
                    provider_name=llm_provider.name,
                    model_name=llm_provider.default_llm_model or "unknown",
                    experiment_id=experiment_id, combination_id=combination_id,
                    metadata={"question": question[:100], "sub_operation": "cag"},
                )
            except Exception:
                pass
            results.append({
                "question": question,
                "answer": response.content,
                "contexts": [full_text[:2000]],  # Truncated context for RAGAS
                "retrieval_ms": 0.0,
                "generation_ms": gen_ms,
                "total_latency_ms": gen_ms,
            })
        return results

    # --- Standard pipeline: chunk, embed, index ---

    # 1. Create embeddings via provider factory (needed before chunking for semantic strategy)
    emb_provider = _resolve_provider(db, embedding_provider_id, capability="embedding", model=embedding_model)
    embeddings = get_embeddings(db, provider_id=embedding_provider_id, model=embedding_model, dimensions=embedding_dimensions)

    # 2. Chunk documents
    chunks = chunk_documents(documents, chunk_size, chunk_overlap, chunking_strategy, embeddings=embeddings)

    # 3. Create vector store and index
    dim_suffix = f"_{embedding_dimensions}" if embedding_dimensions else ""
    collection_name = f"exp_{chunk_size}_{chunk_overlap}_{top_k}_{search_type}_{distance_metric}_{chunking_strategy}{dim_suffix}"
    backend = create_vectorstore_backend(vectorstore_type, vectorstore_config)

    # RAPTOR: build hierarchical summary tree before indexing
    if search_type == "raptor":
        from app.services.raptor_indexer import build_raptor_tree
        llm_for_raptor = get_llm(db, provider_id=llm_provider_id, temperature=0)
        chunks = await build_raptor_tree(
            chunks=chunks,
            embeddings=embeddings,
            llm=llm_for_raptor,
            max_levels=params.get("raptor_max_levels", 3),
            clustering=params.get("raptor_clustering", "kmeans"),
            db=db,
            provider_name=llm_provider.name,
            model_name=llm_provider.default_llm_model or "unknown",
            experiment_id=experiment_id,
            combination_id=combination_id,
        )

    backend.create_collection(collection_name, chunks, embeddings, distance_metric=distance_metric)

    # Log embedding token usage
    chunk_texts = [c.page_content for c in chunks]
    try:
        log_embedding_usage(
            db=db,
            texts=chunk_texts,
            operation="rag_pipeline",
            provider_name=emb_provider.name,
            model_name=embedding_model,
            experiment_id=experiment_id,
            combination_id=combination_id,
            metadata={"num_chunks": len(chunks), "chunk_size": chunk_size},
        )
    except Exception:
        pass  # Don't fail pipeline on logging errors

    # 4. Create LLM via provider factory
    llm = get_llm(db, provider_id=llm_provider_id, temperature=0)

    results = []
    for question in questions:
        # Retrieve relevant documents based on search type
        retrieval_start = time.perf_counter()
        if search_type == "hyde":
            from app.services.hyde_retriever import hyde_retrieve
            retrieved_docs = await hyde_retrieve(
                question=question, backend=backend, llm=llm,
                embeddings=embeddings, top_k=top_k, db=db,
                provider_name=llm_provider.name,
                model_name=llm_provider.default_llm_model or "unknown",
                experiment_id=experiment_id, combination_id=combination_id,
            )
        elif search_type == "crag":
            from app.services.corrective_retriever import crag_retrieve
            retrieved_docs = await crag_retrieve(
                question=question, backend=backend, llm=llm, top_k=top_k,
                relevance_threshold=params.get("crag_relevance_threshold", 0.7),
                max_retries=params.get("crag_max_retries", 2),
                db=db, provider_name=llm_provider.name,
                model_name=llm_provider.default_llm_model or "unknown",
                experiment_id=experiment_id, combination_id=combination_id,
            )
        elif search_type == "self_rag":
            from app.services.corrective_retriever import self_rag_retrieve
            retrieved_docs = await self_rag_retrieve(
                question=question, backend=backend, llm=llm, top_k=top_k,
                retrieval_threshold=params.get("self_rag_retrieval_threshold", 0.5),
                db=db, provider_name=llm_provider.name,
                model_name=llm_provider.default_llm_model or "unknown",
                experiment_id=experiment_id, combination_id=combination_id,
            )
        elif search_type == "raptor":
            from app.services.raptor_indexer import raptor_retrieve
            retrieved_docs = raptor_retrieve(
                question=question, backend=backend, top_k=top_k,
                retrieval_mode=params.get("raptor_retrieval_mode", "collapsed"),
                max_levels=params.get("raptor_max_levels", 3),
            )
        elif search_type == "multi_query":
            from app.services.multi_query_retriever import multi_query_retrieve
            retrieved_docs = await multi_query_retrieve(
                question=question, backend=backend, llm=llm, top_k=top_k,
                multi_query_count=params.get("multi_query_count", 3),
                db=db, provider_name=llm_provider.name,
                model_name=llm_provider.default_llm_model or "unknown",
                experiment_id=experiment_id, combination_id=combination_id,
            )
        elif search_type == "agentic":
            from app.services.agentic_retriever import agentic_retrieve
            retrieved_docs = await agentic_retrieve(
                question=question, backend=backend, llm=llm, top_k=top_k,
                max_steps=params.get("agent_max_steps", 5),
                db=db, provider_name=llm_provider.name,
                model_name=llm_provider.default_llm_model or "unknown",
                experiment_id=experiment_id, combination_id=combination_id,
            )
        elif search_type == "mmr":
            retrieved_docs = backend.mmr_search(question, k=top_k)
        elif search_type == "hybrid":
            retrieved_docs = backend.hybrid_search(question, k=top_k)
        else:
            retrieved_docs = backend.similarity_search(question, k=top_k)

        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000.0

        # Build context from retrieved docs
        context_texts = [doc.page_content for doc in retrieved_docs]
        combined_context = "\n\n".join(context_texts)

        # Generate answer using prompt template
        prompt = _build_prompt(prompt_template, combined_context, question, answer_language)
        gen_start = time.perf_counter()
        response = await llm.ainvoke(prompt)
        generation_ms = (time.perf_counter() - gen_start) * 1000.0

        # Log LLM token usage per question
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
            "retrieval_ms": retrieval_ms,
            "generation_ms": generation_ms,
            "total_latency_ms": retrieval_ms + generation_ms,
        })

    # Cleanup
    try:
        backend.delete_collection(collection_name)
    except Exception:
        pass

    return results
