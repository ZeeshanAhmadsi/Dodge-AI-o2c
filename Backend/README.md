# Dodge AI - Backend

This is the Python FastAPI backend engine for the Dodge AI Order-to-Cash Graph Explorer. It handles the LangChain processing, translating natural language into complex structural Cypher queries to interrogate the Neo4j database.

## 🚀 Architecture

- **FastAPI Core**: Serves the `/api/v1/chat` LLM streaming endpoints.
- **LangChain & Groq**: Uses `llama-3.3-70b-versatile` through the Groq API for lightning-fast natural language to Cypher translation.
- **Graph Ingestion Engine**: Includes `scripts/ingest_graph.py`, a robust processing pipeline that reads gigabytes of flat SAP JSONL exports and maps them into interconnected nodes directly into Neo4j using dynamic property unpacking.

## 📦 Getting Started

### Prerequisites
- Python 3.10+
- A running Neo4j Database instance (AuraDB or local desktop).
- Groq API Key

### Installation

1. Set up a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt 
   # (If requirements missing, manually install fastapi, uvicorn, neo4j, langchain-neo4j, langchain-groq, python-dotenv)
   ```

2. Create a `.env` file containing your database credentials:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password
   GROQ_API_KEY=your_groq_api_key
   ```

### ⚙️ Database Ingestion

To populate your graph, place your SAP generic tables into `sap-o2c-data/` and run the script:
```bash
$env:PYTHONPATH="." 
python scripts/ingest_graph.py
```

### 🏃 Running the Server

Start the Uvicorn ASGI server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
