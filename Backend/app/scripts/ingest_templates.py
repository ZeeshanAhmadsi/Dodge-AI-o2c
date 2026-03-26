import json
import logging
import argparse
from pathlib import Path

from app.core.config import settings
from app.services.rag.ingestion import GenericIngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def ingest_templates(templates_path: str = "app/data/templates/templates.json"):
    """
    Reads templates from JSON and ingests them into the Vector Store
    under the 'templates' namespace using the GenericIngestionService.
    """
    logger.info("Starting template ingestion pipeline...")

    path = Path(templates_path)
    if not path.exists():
        logger.error(f"Templates file not found at {path.absolute()}")
        return

    with open(path, 'r', encoding='utf-8') as f:
        file_content = json.load(f)
        templates = file_content.get("templates", [])

    logger.info(f"Loaded {len(templates)} templates from {templates_path}")

    template_config = {
        "source_name": "templates",
        "record_id_field": "id",
        "text_fields": [
            "id",
            "type",
            "system",
            "prompt"
        ],
        "metadata_fields": [
            "id",
            "type"
        ]
    }

    # Embed raw JSON string into metadata so retrieval can return the full template
    for t in templates:
        t["raw_template"] = json.dumps(t)

    template_config["metadata_fields"].append("raw_template")

    ingestor = GenericIngestionService()  # Uses settings.PINECONE_INDEX_NAME
    result = ingestor.ingest(data=templates, config=template_config)

    logger.info(f"Template ingestion complete: {result.get('chunks_upserted')} chunks upserted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest prompt templates into Pinecone.")
    parser.add_argument(
        "--templates-path",
        type=str,
        default="app/data/templates/templates.json",
        help="Path to the templates JSON file to ingest."
    )
    args = parser.parse_args()
    ingest_templates(args.templates_path)

