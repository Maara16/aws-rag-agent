"""
Vector store management using Chroma for semantic search over AWS SAA documents.
"""

import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(
        self,
        chroma_db_path: str = "data/chroma_db",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        collection_name: str = "aws_saa_docs"
    ):
        self.chroma_db_path = Path(chroma_db_path)
        self.chroma_db_path.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name

        # Initialize embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()

        # Initialize Chroma client
        settings = Settings(
            chroma_db_impl="duckdb",
            persist_directory=str(self.chroma_db_path),
            anonymized_telemetry=False
        )
        self.client = chromadb.Client(settings)

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"Chroma collection '{collection_name}' ready. Dimension: {self.embedding_dim}")

    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict] = None,
        ids: List[str] = None,
        batch_size: int = 100
    ) -> None:
        """Add documents to vector store with batching."""
        if not texts:
            logger.warning("No texts to add")
            return

        if metadatas is None:
            metadatas = [{"source": "aws_saa"} for _ in texts]
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(texts))]

        logger.info(f"Adding {len(texts)} documents to Chroma (batch_size={batch_size})")

        # Process in batches to avoid memory issues
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_metadatas = metadatas[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]

            # Embed batch
            embeddings = self.embedding_model.encode(batch_texts, show_progress_bar=False)
            embeddings = embeddings.tolist()

            # Add to collection
            self.collection.add(
                ids=batch_ids,
                embeddings=embeddings,
                metadatas=batch_metadatas,
                documents=batch_texts
            )
            logger.info(f"  Processed {min(i+batch_size, len(texts))}/{len(texts)}")

        logger.info(f"Successfully added {len(texts)} documents")

    def search(
        self,
        query: str,
        k: int = 5,
        where: Dict = None
    ) -> List[Tuple[str, float, Dict]]:
        """
        Search for similar documents.
        
        Returns:
            List of (document_text, distance, metadata) tuples
        """
        # Embed query
        query_embedding = self.embedding_model.encode([query], show_progress_bar=False)[0]

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=k,
            where=where
        )

        # Parse results
        output = []
        if results["documents"] and len(results["documents"]) > 0:
            for i in range(len(results["documents"][0])):
                text = results["documents"][0][i]
                distance = results["distances"][0][i]  # Lower is better for cosine
                metadata = results["metadatas"][0][i]
                output.append((text, distance, metadata))

        return output

    def hybrid_search(
        self,
        query: str,
        k: int = 5,
        semantic_weight: float = 0.7,
        bm25_weight: float = 0.3
    ) -> List[Tuple[str, float, Dict]]:
        """
        Hybrid search combining semantic and BM25 ranking.
        
        Args:
            query: Search query
            k: Number of results to return
            semantic_weight: Weight for semantic search (0.0-1.0)
            bm25_weight: Weight for BM25 ranking
        """
        # Semantic search (get top 2*k to re-rank)
        semantic_results = self.search(query, k=2*k)

        if not semantic_results:
            return []

        # BM25 re-ranking
        from rank_bm25 import BM25Okapi

        # Get all documents for BM25
        all_docs = self.collection.get()
        if all_docs["documents"]:
            doc_texts = all_docs["documents"]
            tokenized = [doc.split() for doc in doc_texts]
            bm25 = BM25Okapi(tokenized)

            query_tokens = query.lower().split()
            bm25_scores = bm25.get_scores(query_tokens)

            # Normalize scores
            semantic_scores = np.array([1 - r[1] for r in semantic_results])  # Convert distance to similarity
            semantic_scores = (semantic_scores - semantic_scores.min()) / (semantic_scores.max() - semantic_scores.min() + 1e-8)

            # Map BM25 scores to semantic results
            hybrid_scores = []
            for doc_text, _, metadata in semantic_results:
                doc_idx = doc_texts.index(doc_text) if doc_text in doc_texts else -1
                bm25_score = bm25_scores[doc_idx] if doc_idx >= 0 else 0
                bm25_score = bm25_score / (max(bm25_scores) + 1e-8) if max(bm25_scores) > 0 else 0

                combined_score = (semantic_weight * semantic_scores[len(hybrid_scores)] +
                                bm25_weight * bm25_score)
                hybrid_scores.append(combined_score)

            # Re-rank and return top k
            ranked = sorted(
                zip(semantic_results, hybrid_scores),
                key=lambda x: x[1],
                reverse=True
            )
            return [r[0] for r in ranked[:k]]

        return semantic_results[:k]

    def get_stats(self) -> Dict:
        """Get collection statistics."""
        count = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "total_documents": count,
            "embedding_dimension": self.embedding_dim
        }

    def clear(self) -> None:
        """Clear all documents from collection."""
        logger.warning("Clearing all documents from collection")
        all_docs = self.collection.get()
        if all_docs["ids"]:
            self.collection.delete(ids=all_docs["ids"])

    def persist(self) -> None:
        """Persist data to disk."""
        self.client.persist()
        logger.info("Vector store persisted")


# Singleton instance
_vs_instance = None


def get_vector_store(
    chroma_db_path: str = "data/chroma_db",
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    collection_name: str = "aws_saa_docs"
) -> VectorStore:
    """Get or create vector store instance."""
    global _vs_instance
    if _vs_instance is None:
        _vs_instance = VectorStore(chroma_db_path, embedding_model, collection_name)
    return _vs_instance
