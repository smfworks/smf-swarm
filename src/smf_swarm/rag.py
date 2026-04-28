"""SMF Swarm — Local RAG support for report and domain-knowledge ingestion.

Optional extras: chromadb + sentence-transformers.

Usage:
    from smf_swarm.rag import RAGStore
    rag = RAGStore(collection_name="financial")
    rag.add_text("Q1 earnings report: revenue up 15% YoY...", doc_id="q1-2026")
    context = rag.query("What was the revenue growth?", n_results=3)
"""

from __future__ import annotations

import os
import hashlib
from typing import Optional

from smf_swarm.platform_paths import default_cache_dir


class RAGStore:
    """Optional local ChromaDB-backed RAG for SMF Swarm."""

    def __init__(self, collection_name: str = "smf_swarm", persist_dir: Optional[str] = None):
        self.collection_name = collection_name
        self.persist_dir = persist_dir or os.path.join(default_cache_dir(), "rag")
        os.makedirs(self.persist_dir, exist_ok=True)

        self._client = None
        self._collection = None

    def _init_client(self):
        if self._client is not None:
            return
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"source": "smf-swarm"},
            )
        except ImportError:
            self._client = False
            self._collection = False

    @property
    def available(self) -> bool:
        self._init_client()
        return self._client is not False

    def _embed_fn(self):
        """Lazy-init embedding model."""
        try:
            from sentence_transformers import SentenceTransformer
            # Lightweight model, downloads on first use (~80 MB)
            return SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            return None

    def add_text(self, text: str, doc_id: Optional[str] = None, metadata: Optional[dict] = None):
        """Add a document chunk to the RAG store."""
        if not self.available:
            return False
        doc_id = doc_id or hashlib.sha256(text.encode()).hexdigest()[:16]
        embed_fn = self._embed_fn()
        if embed_fn is None:
            return False
        embedding = embed_fn.encode(text, convert_to_list=True)
        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata or {}],
        )
        return True

    def add_pdf_text(self, pdf_text: str, chunk_size: int = 500, metadata: Optional[dict] = None):
        """Chunk and ingest a PDF/TXT/Markdown transcript."""
        chunks = [pdf_text[i:i+chunk_size] for i in range(0, len(pdf_text), chunk_size)]
        for i, chunk in enumerate(chunks):
            self.add_text(chunk, doc_id=f"chunk_{i}", metadata=metadata)
        return len(chunks)

    def query(self, q: str, n_results: int = 3) -> dict:
        """Retrieve top-k relevant chunks for a query."""
        if not self.available:
            return {"results": [], "error": "RAG not available: install with pip install smf-swarm[rag]"}
        embed_fn = self._embed_fn()
        if embed_fn is None:
            return {"results": [], "error": "Embedding model not available: install with pip install smf-swarm[rag]"}
        embedding = embed_fn.encode(q, convert_to_list=True)
        results = self._collection.query(query_embeddings=[embedding], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return {
            "results": [
                {"text": d, "metadata": m} for d, m in zip(docs, metas)
            ],
            "error": None,
        }

    def clear(self):
        """Drop and recreate the collection."""
        if not self.available:
            return False
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(name=self.collection_name)
        return True
