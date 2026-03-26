import json
import logging
import argparse
from pathlib import Path

from app.services.rag.ingestion import GenericIngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_ingestion(questions_path: str = None):
    """Ingest lead management questions into Pinecone for analytical query classification."""
    if questions_path is None:
        # Default: app/data/questions.json
        questions_path = str(Path(__file__).parent.parent / "data" / "questions.json")

    path = Path(questions_path)
    if not path.exists():
        logger.error(f"Questions file not found at {path.absolute()}")
        return

    with open(path, 'r') as f:
        try:
            questions_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            return

    logger.info(f"Starting ingestion of {len(questions_data)} questions...")

    ingestion_service = GenericIngestionService()  # Uses settings.PINECONE_INDEX_NAME

    config = {
        "source_name": "lead-management-questions",
        "record_id_field": "question",
        "text_fields": ["question"],
        "metadata_fields": ["type"]
    }

    try:
        result = ingestion_service.ingest(questions_data, config)
        logger.info(f"Ingestion complete — Status: {result['status']}, Chunks: {result['chunks_upserted']}, Namespace: {result['namespace']}")
    except Exception as e:
        logger.error(f"An error occurred during ingestion: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest LMS questions into Pinecone for classification.")
    parser.add_argument(
        "--questions-path",
        type=str,
        default=None,
        help="Path to the questions JSON file. Defaults to app/data/questions.json"
    )
    args = parser.parse_args()
    run_ingestion(args.questions_path)
