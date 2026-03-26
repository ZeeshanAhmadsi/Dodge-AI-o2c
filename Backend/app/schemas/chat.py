from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class ChatRequest(BaseModel):
    question: str = Field(..., description="The user's question to the RAG system.")

class ChatResponse(BaseModel):
    answer: str = Field(..., description="The generated answer from the LLM.")
    status: str = Field(..., description="The status of the request (e.g., 'success', 'error').")
    latency_seconds: float = Field(..., description="Total time taken to process the request.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional debug metrics and metadata.")
