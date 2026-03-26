import os
import logging
from dotenv import load_dotenv
load_dotenv()

from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_core.prompts.prompt import PromptTemplate
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

CYPHER_GENERATION_TEMPLATE = """Task:Generate Cypher statement to query a graph database.
Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.
CRITICAL: Do NOT use variables or Neo4j parameters like $id or $name in your Cypher query. You MUST hardcode strings and values directly into the MATCH query.
CRITICAL FORMATTING: NEVER enclose your generated Cypher statement in markdown code blocks like ```cypher. You MUST output ONLY the raw Cypher query string.
CRITICAL NEO4J SYNTAX: 
1. PatternExpressions are not allowed to introduce new variables in a WHERE clause. If you check for missing relationships using WHERE NOT EXISTS, DO NOT declare new variables inside the EXISTS block. For example, instead of WHERE NOT EXISTS {{ (a)-[]->(b:Node) }}, use WHERE NOT EXISTS {{ (a)-[]->(:Node) }}.
2. For "broken flow" queries, evaluate the existence of connected nodes using OPTIONAL MATCH with assigned variables. NEVER use inline pattern expressions like `(so)-[:INCLUDES]->(:Product) IS NULL` in a RETURN or WHERE clause. Instead, assign variables in OPTIONAL MATCH and use `IS NULL`. For example: `MATCH (so:SalesOrder) OPTIONAL MATCH (so)-[:INCLUDES]->(p:Product) RETURN so.id, p IS NULL AS isMissingProduct`.
CRITICAL UNION SYNTAX: If you use a UNION statement, ALL sub-queries inside the UNION MUST have the exact same return column aliases (e.g., use 'AS' to ensure variables perfectly match).
Schema:
{schema}
Note: Do not include any explanations or apologies in your responses.
Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.
Do not include any text except the generated Cypher statement.
The question is:
{question}"""

CYPHER_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question"], template=CYPHER_GENERATION_TEMPLATE
)

QA_TEMPLATE = """You are a data analyst answering a user's question based on the raw database results provided below.
The database has already run the correct query. The 'Information' section contains the EXACT results from the database that answer their question.
You must use this Information to answer the user's question directly. Do not explain the database schema or say 'based on the information'. Just provide the final answer naturally.
If the Information is a list of records, summarize them or list them clearly.
If the Information is empty, say "No matching records found."

Information:
{context}

Question: {question}
Helpful Answer:"""

QA_PROMPT = PromptTemplate(input_variables=["context", "question"], template=QA_TEMPLATE)

def get_graph_qa_chain():
    graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
    graph.refresh_schema()

    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY is not set. The LLM connection will fail. Please add it to your .env file.")
        
    llm = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.3-70b-versatile", temperature=0)
    
    chain = GraphCypherQAChain.from_llm(
        cypher_llm=llm,
        qa_llm=llm,
        graph=graph,
        verbose=True,
        cypher_prompt=CYPHER_GENERATION_PROMPT,
        qa_prompt=QA_PROMPT,
        allow_dangerous_requests=True 
    )
    return chain

def process_chat_query(query: str):
    # Guardrail check
    lower_q = query.lower()
    off_topic_words = ["joke", "poem", "write me code", "write code", "how are you", "what is the meaning of life"]
    if any(word in lower_q for word in off_topic_words):
        return "This system is designed to answer questions related to the provided dataset only."
        
    try:
        chain = get_graph_qa_chain()
        result = chain.invoke({"query": query})
        return result["result"]
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return f"Sorry, I encountered an error translating your natural language into a Graph Query: {str(e)}"
