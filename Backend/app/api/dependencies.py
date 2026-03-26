from fastapi import Depends
import logging

from app.core.config import settings
from app.services.rag.embeddings import EmbeddingService
from app.services.rag.vectorstore import VectorStoreService
from app.services.rag.template_retriever import TemplateRetrieverService
from app.services.rag.context_retriever import ContextRetrieverService
from app.services.reasoning.orchestrator import LLMOrchestratorService
from app.services.chat.history_service import HistoryService

logger = logging.getLogger(__name__)

# Global instances for the singleton pattern (lazy initialization)
_embedder: EmbeddingService | None = None
_vector_store: VectorStoreService | None = None
_template_retriever: TemplateRetrieverService | None = None
_context_retriever: ContextRetrieverService | None = None
_llm_orchestrator: LLMOrchestratorService | None = None
_history_service: HistoryService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedder
    if _embedder is None:
        logger.info("Initializing EmbeddingService")
        _embedder = EmbeddingService()
    return _embedder

def get_vector_store_service() -> VectorStoreService:
    global _vector_store
    if _vector_store is None:
        logger.info("Initializing VectorStoreService")
        _vector_store = VectorStoreService(index_name=settings.PINECONE_INDEX_NAME)
    return _vector_store

def get_template_retriever(
    embedder: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStoreService = Depends(get_vector_store_service)
) -> TemplateRetrieverService:
    global _template_retriever
    if _template_retriever is None:
        logger.info("Initializing TemplateRetrieverService")
        _template_retriever = TemplateRetrieverService(
            embedder=embedder,
            vector_store=vector_store
        )
    return _template_retriever

def get_context_retriever(
    embedder: EmbeddingService = Depends(get_embedding_service),
    vector_store: VectorStoreService = Depends(get_vector_store_service)
) -> ContextRetrieverService:
    global _context_retriever
    if _context_retriever is None:
        logger.info("Initializing ContextRetrieverService")
        _context_retriever = ContextRetrieverService(
            embedder=embedder,
            vector_store=vector_store
        )
    return _context_retriever

def get_llm_orchestrator(
    template_retriever: TemplateRetrieverService = Depends(get_template_retriever),
    context_retriever: ContextRetrieverService = Depends(get_context_retriever)
) -> LLMOrchestratorService:
    global _llm_orchestrator
    if _llm_orchestrator is None:
        logger.info("Initializing LLMOrchestratorService")
        _llm_orchestrator = LLMOrchestratorService(
            template_retriever=template_retriever,
            context_retriever=context_retriever
        )
    return _llm_orchestrator


def get_history_service() -> HistoryService:
    """Lazy singleton — HistoryService is stateless (all state in Redis/Postgres)."""
    global _history_service
    if _history_service is None:
        logger.info("Initializing HistoryService")
        _history_service = HistoryService()
    return _history_service
