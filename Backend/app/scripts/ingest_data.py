import json
import logging
import argparse
from pathlib import Path
from pprint import pformat

from app.core.config import settings
from app.services.rag.ingestion import GenericIngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def run_ingest(data_path: str):
    """
    Runs the GenericIngestionService on the leads dataset.
    """
    path = Path(data_path)
    if not path.exists():
        logger.error(f"Data file not found at {path.absolute()}")
        return

    with open(path, 'r', encoding='utf-8') as f:
        data_records = json.load(f)

    if not isinstance(data_records, list) or not data_records:
        logger.error("No records found in data file (expected a JSON list).")
        return

    logger.info(f"Loaded {len(data_records)} records from {data_path}")

    ingestion_config = {
        "source_name": "leads",
        "record_id_field": "lead_id",
        "text_fields": [
            "customer_info.name",
            "interested_model",
            "customer_intent",
            "call_transcript",
            "stage",
            "next_best_action",
            "call_summary.customer_attitude",
            "call_summary.primary_objection",
            "call_summary.buying_signal"
        ],
        "metadata_fields": [
            "lead_id",
            "lead_source",
            "customer_info.city",
            "customer_info.budget_range",
            "assigned_agent",
            "lead_score",
            "call_summary.conversion_probability",
            "call_summary.call_outcome"
        ]
    }

    logger.info(f"Using ingestion config:\n{pformat(ingestion_config)}")

    ingestor = GenericIngestionService()  # Uses settings.PINECONE_INDEX_NAME
    result = ingestor.ingest(data=data_records, config=ingestion_config)

    logger.info(f"Ingestion complete: {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest lead data into Pinecone.")
    parser.add_argument(
        "--data-path",
        type=str,
        default="app/data/appdata/data.json",
        help="Path to the JSON data file to ingest."
    )
    args = parser.parse_args()
    run_ingest(args.data_path)

