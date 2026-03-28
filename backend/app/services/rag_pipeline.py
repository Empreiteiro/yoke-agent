"""RAG pipeline execution with configurable hyperparameters."""

from typing import List, Dict, Any, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter, TokenTextSplitter
from langchain.schema import Document
from sqlalchemy.orm import Session

from app.services.llm_factory import get_llm, get_embeddings, _resolve_provider
from app.services.vectorstore_factory import create_vectorstore_backend
from app.services.token_tracker import log_llm_response, log_embedding_usage


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

    # 1. Create embeddings via provider factory (needed before chunking for semantic strategy)
    embeddings = get_embeddings(db, provider_id=embedding_provider_id, model=embedding_model, dimensions=embedding_dimensions)

    # 2. Chunk documents
    chunks = chunk_documents(documents, chunk_size, chunk_overlap, chunking_strategy, embeddings=embeddings)

    # Resolve provider info for token logging
    emb_provider = _resolve_provider(db, embedding_provider_id, capability="embedding", model=embedding_model)
    llm_provider = _resolve_provider(db, llm_provider_id, capability="llm")

    # 3. Create vector store and index
    dim_suffix = f"_{embedding_dimensions}" if embedding_dimensions else ""
    collection_name = f"exp_{chunk_size}_{chunk_overlap}_{top_k}_{search_type}_{distance_metric}_{chunking_strategy}{dim_suffix}"
    backend = create_vectorstore_backend(vectorstore_type, vectorstore_config)
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
        if search_type == "mmr":
            retrieved_docs = backend.mmr_search(question, k=top_k)
        elif search_type == "hybrid":
            retrieved_docs = backend.hybrid_search(question, k=top_k)
        else:
            retrieved_docs = backend.similarity_search(question, k=top_k)

        # Build context from retrieved docs
        context_texts = [doc.page_content for doc in retrieved_docs]
        combined_context = "\n\n".join(context_texts)

        # Generate answer
        prompt = f"""Based on the following context, answer the question.
If the answer cannot be found in the context, say "I cannot find the answer in the provided context."

Context:
{combined_context}

Question: {question}

Answer:"""

        response = await llm.ainvoke(prompt)

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
        })

    # Cleanup
    try:
        backend.delete_collection(collection_name)
    except Exception:
        pass

    return results
