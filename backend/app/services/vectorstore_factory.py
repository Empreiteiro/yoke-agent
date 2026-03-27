"""Vector store abstraction layer with pluggable backends."""

from typing import List, Optional, Dict, Any, Protocol
from abc import ABC, abstractmethod

from langchain.schema import Document
from langchain_core.embeddings import Embeddings


class VectorStoreBackend(ABC):
    """Abstract base class for vector store backends."""

    @abstractmethod
    def create_collection(self, name: str, documents: List[Document], embeddings: Embeddings) -> None:
        """Create a new collection and index documents."""
        pass

    @abstractmethod
    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        """Perform similarity search."""
        pass

    @abstractmethod
    def hybrid_search(self, query: str, k: int = 5) -> List[Document]:
        """Perform hybrid search (vector + keyword)."""
        pass

    @abstractmethod
    def mmr_search(self, query: str, k: int = 5) -> List[Document]:
        """Perform Maximum Marginal Relevance search."""
        pass

    @abstractmethod
    def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        pass


class ChromaDBBackend(VectorStoreBackend):
    """ChromaDB vector store backend (default)."""

    def __init__(self, persist_directory: str = "./chroma_data"):
        self.persist_directory = persist_directory
        self._vectorstore = None

    def create_collection(self, name: str, documents: List[Document], embeddings: Embeddings) -> None:
        from langchain_community.vectorstores import Chroma

        self._vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            collection_name=name,
            persist_directory=self.persist_directory,
        )

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        if not self._vectorstore:
            raise RuntimeError("Collection not initialized. Call create_collection first.")
        return self._vectorstore.similarity_search(query, k=k)

    def hybrid_search(self, query: str, k: int = 5) -> List[Document]:
        # ChromaDB doesn't natively support hybrid search; fall back to similarity
        return self.similarity_search(query, k=k)

    def mmr_search(self, query: str, k: int = 5) -> List[Document]:
        if not self._vectorstore:
            raise RuntimeError("Collection not initialized. Call create_collection first.")
        return self._vectorstore.max_marginal_relevance_search(query, k=k)

    def delete_collection(self, name: str) -> None:
        if self._vectorstore:
            self._vectorstore.delete_collection()
            self._vectorstore = None


class PineconeBackend(VectorStoreBackend):
    """Pinecone vector store backend."""

    def __init__(self, api_key: str, environment: str, index_name: str):
        self.api_key = api_key
        self.environment = environment
        self.index_name = index_name
        self._vectorstore = None

    def create_collection(self, name: str, documents: List[Document], embeddings: Embeddings) -> None:
        from langchain_community.vectorstores import Pinecone

        self._vectorstore = Pinecone.from_documents(
            documents=documents,
            embedding=embeddings,
            index_name=self.index_name,
            namespace=name,
        )

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        if not self._vectorstore:
            raise RuntimeError("Collection not initialized.")
        return self._vectorstore.similarity_search(query, k=k)

    def hybrid_search(self, query: str, k: int = 5) -> List[Document]:
        return self.similarity_search(query, k=k)

    def mmr_search(self, query: str, k: int = 5) -> List[Document]:
        if not self._vectorstore:
            raise RuntimeError("Collection not initialized.")
        return self._vectorstore.max_marginal_relevance_search(query, k=k)

    def delete_collection(self, name: str) -> None:
        self._vectorstore = None


class QdrantBackend(VectorStoreBackend):
    """Qdrant vector store backend."""

    def __init__(self, url: str, api_key: Optional[str] = None, collection_name: str = "default"):
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self._vectorstore = None

    def create_collection(self, name: str, documents: List[Document], embeddings: Embeddings) -> None:
        from langchain_community.vectorstores import Qdrant

        self._vectorstore = Qdrant.from_documents(
            documents=documents,
            embedding=embeddings,
            url=self.url,
            api_key=self.api_key,
            collection_name=name,
        )

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        if not self._vectorstore:
            raise RuntimeError("Collection not initialized.")
        return self._vectorstore.similarity_search(query, k=k)

    def hybrid_search(self, query: str, k: int = 5) -> List[Document]:
        return self.similarity_search(query, k=k)

    def mmr_search(self, query: str, k: int = 5) -> List[Document]:
        if not self._vectorstore:
            raise RuntimeError("Collection not initialized.")
        return self._vectorstore.max_marginal_relevance_search(query, k=k)

    def delete_collection(self, name: str) -> None:
        self._vectorstore = None


class WeaviateBackend(VectorStoreBackend):
    """Weaviate vector store backend."""

    def __init__(self, url: str, api_key: Optional[str] = None, class_name: str = "Document"):
        self.url = url
        self.api_key = api_key
        self.class_name = class_name
        self._vectorstore = None

    def create_collection(self, name: str, documents: List[Document], embeddings: Embeddings) -> None:
        from langchain_community.vectorstores import Weaviate
        import weaviate

        auth = weaviate.AuthApiKey(api_key=self.api_key) if self.api_key else None
        client = weaviate.Client(url=self.url, auth_client_secret=auth)

        self._vectorstore = Weaviate.from_documents(
            documents=documents,
            embedding=embeddings,
            client=client,
            index_name=name,
        )

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        if not self._vectorstore:
            raise RuntimeError("Collection not initialized.")
        return self._vectorstore.similarity_search(query, k=k)

    def hybrid_search(self, query: str, k: int = 5) -> List[Document]:
        return self.similarity_search(query, k=k)

    def mmr_search(self, query: str, k: int = 5) -> List[Document]:
        if not self._vectorstore:
            raise RuntimeError("Collection not initialized.")
        return self._vectorstore.max_marginal_relevance_search(query, k=k)

    def delete_collection(self, name: str) -> None:
        self._vectorstore = None


class PGVectorBackend(VectorStoreBackend):
    """PGVector (PostgreSQL) vector store backend."""

    def __init__(self, connection_string: str, collection_name: str = "documents"):
        self.connection_string = connection_string
        self.collection_name = collection_name
        self._vectorstore = None

    def create_collection(self, name: str, documents: List[Document], embeddings: Embeddings) -> None:
        from langchain_community.vectorstores import PGVector

        self._vectorstore = PGVector.from_documents(
            documents=documents,
            embedding=embeddings,
            connection_string=self.connection_string,
            collection_name=name,
        )

    def similarity_search(self, query: str, k: int = 5) -> List[Document]:
        if not self._vectorstore:
            raise RuntimeError("Collection not initialized.")
        return self._vectorstore.similarity_search(query, k=k)

    def hybrid_search(self, query: str, k: int = 5) -> List[Document]:
        return self.similarity_search(query, k=k)

    def mmr_search(self, query: str, k: int = 5) -> List[Document]:
        if not self._vectorstore:
            raise RuntimeError("Collection not initialized.")
        return self._vectorstore.max_marginal_relevance_search(query, k=k)

    def delete_collection(self, name: str) -> None:
        self._vectorstore = None


def create_vectorstore_backend(
    store_type: str,
    config: Optional[Dict[str, Any]] = None,
) -> VectorStoreBackend:
    """Factory function to create a vector store backend."""
    config = config or {}

    backends = {
        "chromadb": lambda: ChromaDBBackend(
            persist_directory=config.get("persist_directory", "./chroma_data"),
        ),
        "pinecone": lambda: PineconeBackend(
            api_key=config["api_key"],
            environment=config["environment"],
            index_name=config["index_name"],
        ),
        "qdrant": lambda: QdrantBackend(
            url=config.get("url", "http://localhost:6333"),
            api_key=config.get("api_key"),
            collection_name=config.get("collection_name", "default"),
        ),
        "weaviate": lambda: WeaviateBackend(
            url=config.get("url", "http://localhost:8080"),
            api_key=config.get("api_key"),
            class_name=config.get("class_name", "Document"),
        ),
        "pgvector": lambda: PGVectorBackend(
            connection_string=config["connection_string"],
            collection_name=config.get("collection_name", "documents"),
        ),
    }

    factory = backends.get(store_type)
    if factory is None:
        raise ValueError(f"Unsupported vector store type: {store_type}. Supported: {list(backends.keys())}")

    return factory()
