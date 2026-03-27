"""RAG pipeline execution with configurable hyperparameters."""

from typing import List, Dict, Any

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA

from app.core.config import settings
from app.services.vectorstore_factory import create_vectorstore_backend


def get_embeddings(model_name: str) -> OpenAIEmbeddings:
    """Get an embeddings instance for the given model."""
    return OpenAIEmbeddings(
        model=model_name,
        api_key=settings.openai_api_key,
    )


def chunk_documents(
    documents: List[Document],
    chunk_size: int,
    chunk_overlap_pct: int,
) -> List[Document]:
    """Split documents into chunks with given size and overlap."""
    overlap = int(chunk_size * chunk_overlap_pct / 100)
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
    vectorstore_type: str = "chromadb",
    vectorstore_config: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Run a RAG pipeline with the given parameters and return answers for each question.

    Args:
        documents: Source documents to index
        questions: List of questions to answer
        params: RAG hyperparameters (chunk_size, chunk_overlap, embedding_model, top_k, search_type)
        vectorstore_type: Type of vector store to use
        vectorstore_config: Optional vector store configuration

    Returns:
        List of dicts with 'question', 'answer', and 'contexts' for each question
    """
    chunk_size = params["chunk_size"]
    chunk_overlap = params["chunk_overlap"]
    embedding_model = params["embedding_model"]
    top_k = params["top_k"]
    search_type = params["search_type"]

    # 1. Chunk documents
    chunks = chunk_documents(documents, chunk_size, chunk_overlap)

    # 2. Create embeddings
    embeddings = get_embeddings(embedding_model)

    # 3. Create vector store and index
    collection_name = f"exp_{chunk_size}_{chunk_overlap}_{top_k}_{search_type}"
    backend = create_vectorstore_backend(vectorstore_type, vectorstore_config)
    backend.create_collection(collection_name, chunks, embeddings)

    # 4. Run queries
    llm = ChatOpenAI(
        model=settings.default_llm_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )

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
