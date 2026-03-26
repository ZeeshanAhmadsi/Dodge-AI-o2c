# RAG Chatbot Service

A modular, production-ready Retrieval-Augmented Generation (RAG) chatbot backend system built natively with Python, `langchain`, and Hugging Face.

## 🏗️ Architecture

The project has been architected strictly adhering to the Single Responsibility Principle, aggressively decoupling database ORM mapping, chunking logic, and embedding inferences, allowing components to scale dynamically.

```text
swiftex-sense/
│
├── app/
│   ├── main.py                # Main execution script / Sandbox tests
│   │
│   ├── core/
│   │   └── config.py          # Centralized Environment Loading Validation
│   │
│   ├── services/
│   │   ├── rag/
│   │   │   ├── chunking.py    # Isolated text-splitting using LangChain
│   │   │   └── embeddings.py  # Isolated Vector generation using Hugging Face
│   │   │
│   │   ├── llm.py             # Open placeholder for Chatbot LLM calls
│   │   ├── validator.py       # Open placeholder for Response Validation
│   │   └── fallback.py        # Open placeholder for Agentic guardrails
│   │
│   └── data/
│       └── templates.json     # Configuration file for static instruction prompting
│
├── .env                       # Local secrets (ignored by Git)
├── requirements.txt           # Standardized PIP dependencies
└── README.md                  # Documentation File
```

## 🚀 Setup & Installation

### 1. Prerequisites
Ensure you have Python installed and create a Virtual Environment:
```bash
python -m venv venv
```

### 2. Activate the Environment
* **Windows CMD:** `venv\Scripts\activate`
* **Windows PowerShell:** `.\venv\Scripts\Activate.ps1`
* **macOS/Linux:** `source venv/bin/activate`

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file at the root of your project matching the following schema. You can acquire a free token from the [Hugging Face Settings Page](https://huggingface.co/settings/tokens).

```env
APP_ENV=development

# Hugging Face Settings
HUGGINGFACE_API_KEY=your_hf_key_here
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# RAG Chunk Settings
CHUNK_SIZE=1000
CHUNK_OVERLAP=150
```

## 📚 Core Services Overview

### `ChunkingService` (`app/services/rag/chunking.py`)
Responsible exclusively for manipulating and splitting large text corpuses down to token-friendly sizes.
* Parses variables intelligently against NLP contexts instead of hard line-breaks utilizing `RecursiveCharacterTextSplitter`.
* Supports singular string ingestion (`split_text()`) or iterating over document datasets (`split_documents()`).

### `EmbeddingService` (`app/services/rag/embeddings.py`)
Responsible exclusively for talking with Hugging Face Inference endpoints and retrieving deep-learning Vector matrices representation of text strings.
* Decoupled completely from upstream DB logic constraints.
* Built dynamically utilizing `HuggingFaceEndpointEmbeddings`.

## 📊 Analytical Chatbot API

The system now includes a FastAPI-based backend that supports session-based conversation history ("back-to-back messages").

### 🔌 Running the API
1. Ensure dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the API server:
   ```bash
   python analytical/api.py
   ```
   *The server will start on `http://127.0.0.1:8000`*

### 📩 API Endpoints
- `GET /sessions/new`: Generates a new `session_id`.
- `POST /api/chat`: Send a query with an optional `session_id`.
- `GET /api/history/{session_id}`: Retrieve chat history.

### 🧪 Testing the API
Once the server is running, you can test the conversation flow using:
```bash
python analytical/test_api.py
```

## 🎛️ Production API Server (FastAPI)
The main backend service has been modularized into a production-ready FastAPI application.

### 🔌 Running the Server
You can run the interactive API server using Uvicorn:
```bash
uvicorn app.main:app --reload
```
Once started, the API will be available at `http://127.0.0.1:8000`.

### 📚 Interactive Documentation
FastAPI automatically generates interactive API documentation.
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

