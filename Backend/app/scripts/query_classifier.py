"""
Query Classifier CLI — development/debugging tool.
Lets you test how a query is classified (analytical vs reasoning) by the vector store.
"""
import logging
import argparse

from app.services.rag.embeddings import EmbeddingService
from app.services.rag.vectorstore import VectorStoreService
from app.services.analytical.relevance import QueryRelevanceService
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.5


def run_classifier():
    logger.info("Initializing services...")
    embedder = EmbeddingService()
    vector_store = VectorStoreService(index_name=settings.PINECONE_INDEX_NAME)
    relevance_service = QueryRelevanceService()

    namespace = settings.ANALYTICAL_QUESTIONS_NAMESPACE

    logger.info("Starting Query Classifier. Type 'exit' to quit.")

    while True:
        try:
            user_input = input("\nEnter your query: ")

            if user_input.lower() in ['exit', 'quit', 'q']:
                break

            if not user_input.strip():
                logger.warning("Query cannot be empty.")
                continue

            # Stage 0: Relevance check
            relevance_result = relevance_service.check_relevance(user_input)

            if not relevance_result.is_relevant:
                logger.info(f"REJECTED (OUT OF SCOPE) — Reason: {relevance_result.reason} | Confidence: {relevance_result.confidence:.2f}")
                continue

            logger.info(f"Query is relevant. Confidence: {relevance_result.confidence:.2f}")

            query_vector = embedder.embed_query(user_input)
            search_results = vector_store.similarity_search_by_vector(
                query_vector=query_vector,
                top_k=3,
                namespace=namespace
            )

            if not search_results:
                logger.info("No relevant questions found in the vector database.")
                continue

            best_match = search_results[0]
            best_score = best_match.get('score', 0)
            best_metadata = best_match.get('metadata', {})

            if best_score < SIMILARITY_THRESHOLD:
                logger.warning(f"LOW SIMILARITY ({best_score:.4f} < {SIMILARITY_THRESHOLD}). Query may be an outlier.")

            for i, result in enumerate(search_results):
                score = result.get('score', 0)
                metadata = result.get('metadata', {})
                text = metadata.get('text', 'N/A')
                q_type = metadata.get('type', 'Unknown')
                logger.info(f"Result {i+1}: Score={score:.4f} | Type={q_type.upper()} | Q: {text}")

            logger.info(f"Best Classification: {best_metadata.get('type', 'Unknown').upper()} | Score: {best_score:.4f}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"An error occurred: {e}")


if __name__ == "__main__":
    run_classifier()
