from fastapi import APIRouter
from pydantic import BaseModel
from app.services.graph_service import get_neo4j_conn
from app.services.llm import process_chat_query
from app.schemas.chat import ChatRequest, ChatResponse

api_router = APIRouter()

@api_router.get("/graph", tags=["Graph"])
async def get_graph():
    conn = get_neo4j_conn()
    data = conn.get_graph_data()
    return data

@api_router.post("/chat", tags=["Chat"])
async def chat(req: ChatRequest):
    response = process_chat_query(req.question)
    return ChatResponse(
        answer=response,
        status="success",
        latency_seconds=0.0  # TODO: Add actual latency tracking
    )
