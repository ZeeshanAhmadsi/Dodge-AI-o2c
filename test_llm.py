import sys
from app.services.llm import process_chat_query

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = sys.argv[1]
        print(f"Query: {query}")
        result = process_chat_query(query)
        print(f"Result: {result}")
    else:
        print("Please provide a query")
