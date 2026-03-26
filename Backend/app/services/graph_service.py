import os
import logging
from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

class Neo4jConnection:
    def __init__(self):
        self.driver = None
        try:
            self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
            logger.info("Neo4j driver initialized.")
        except Exception as e:
            logger.error(f"Failed to create Neo4j driver: {e}")

    def close(self):
        if self.driver is not None:
            self.driver.close()
            logger.info("Neo4j driver closed.")

    def get_graph_data(self):
        """
        Fetches a subset of nodes and edges for the frontend visualization.
        """
        if not self.driver:
            return {"nodes": [], "edges": []}
            
        nodes = []
        edges = []
        
        try:
            with self.driver.session(database=NEO4J_DATABASE) as session:
                # Fetch connected flow paths (Customer -> SalesOrder -> Delivery -> etc)
                # to ensure the UI graph renders an interconnected web rather than isolated stars.
                query = """
                MATCH p=(c:Customer)-[*1..4]->(endNode)
                UNWIND relationships(p) AS r
                RETURN DISTINCT startNode(r) AS n, r, endNode(r) AS m
                LIMIT 300
                """
                result = session.run(query)
                nodes_map = {}
                
                for record in result:
                    n = record["n"]
                    m = record["m"]
                    r = record["r"]
                    
                    if n.id not in nodes_map:
                        nodes_map[n.id] = {
                            "id": str(n.id),
                            "label": list(n.labels)[0] if n.labels else "Unknown",
                            "title": dict(n)
                        }
                    if m.id not in nodes_map:
                        nodes_map[m.id] = {
                            "id": str(m.id),
                            "label": list(m.labels)[0] if m.labels else "Unknown",
                            "title": dict(m)
                        }
                        
                    edges.append({
                        "source": str(n.id),
                        "target": str(m.id),
                        "label": r.type
                    })
                    
                nodes = list(nodes_map.values())
                
        except Exception as e:
            logger.error(f"Failed to fetch graph data: {e}")
            
        return {"nodes": nodes, "edges": edges}

neo4j_conn = Neo4jConnection()

def get_neo4j_conn():
    return neo4j_conn
