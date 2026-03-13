"""
RAG retrieval — pulls pharmacology context from rag_chunks table.
Used only by the agent when DB severity is UNKNOWN.
"""
from app.config import RAG_CHUNK_LIMIT
from app.db.queries import query_rag_chunks, query_rag_chunks_by_name


def retrieve_context(
    drug1: str,
    drug2: str,
    rxcui1: str | None = None,
    rxcui2: str | None = None,
) -> str:
    """
    Returns concatenated RAG chunks for the drug pair.
    Prefers RXCUI lookup (exact); falls back to name-based LIKE match.
    """
    chunks: list[str] = []

    if rxcui1 and rxcui2:
        chunks = query_rag_chunks(rxcui1, rxcui2, limit=RAG_CHUNK_LIMIT)

    if not chunks:
        chunks = query_rag_chunks_by_name(drug1, drug2, limit=RAG_CHUNK_LIMIT)

    return "\n\n---\n\n".join(chunks) if chunks else ""
