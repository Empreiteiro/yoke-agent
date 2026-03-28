"""Document loading and text extraction service."""

import os
from typing import List

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document


LOADER_MAP = {
    ".pdf": PyPDFLoader,
    ".txt": TextLoader,
    ".md": TextLoader,
    ".mdx": TextLoader,
    ".docx": TextLoader,
}


def load_document(filepath: str) -> List[Document]:
    """Load a document and return LangChain Document objects."""
    ext = os.path.splitext(filepath)[1].lower()
    loader_cls = LOADER_MAP.get(ext)

    if loader_cls is None:
        # Fallback to text loader
        loader_cls = TextLoader

    loader = loader_cls(filepath)
    return loader.load()


def load_documents(filepaths: List[str]) -> List[Document]:
    """Load multiple documents and return combined LangChain Document objects."""
    all_docs = []
    for filepath in filepaths:
        if os.path.exists(filepath):
            docs = load_document(filepath)
            all_docs.extend(docs)
    return all_docs
