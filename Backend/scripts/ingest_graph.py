import os
import json
import logging
from pathlib import Path
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

DATA_DIR = Path(__file__).parent.parent / "sap-o2c-data"

def iter_jsonl(directory: Path):
    if not directory.exists():
        logger.warning(f"Directory {directory} not found")
        return
    for file_path in directory.glob("*.jsonl"):
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)

def flatten_props(row):
    return {k: (v if not isinstance(v, (dict, list)) else json.dumps(v)) for k, v in row.items() if v is not None}

def run_ingestion():
    logger.info("Connecting to Neo4j...")
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    logger.info("Connected successfully.")

    with driver.session() as session:
        # Create Indexes for performance
        session.run("CREATE INDEX IF NOT EXISTS FOR (c:Customer) ON (c.id)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (p:Product) ON (p.id)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (s:SalesOrder) ON (s.id)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (d:Delivery) ON (d.id)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (b:BillingDocument) ON (b.id)")

        # 1. Business Partners (Customers)
        logger.info("Ingesting Business Partners (Customers)...")
        for row in iter_jsonl(DATA_DIR / "business_partners"):
            customer_id = row.get("businessPartner")
            
            query = """
            MERGE (c:Customer {id: $customer_id})
            SET c += $props
            """
            session.run(query, customer_id=customer_id, props=flatten_props(row))

        # 2. Products
        logger.info("Ingesting Products...")
        for row in iter_jsonl(DATA_DIR / "products"):
            product_id = row.get("product")
            
            query = """
            MERGE (p:Product {id: $product_id})
            SET p += $props
            """
            session.run(query, product_id=product_id, props=flatten_props(row))

        # 3. Sales Order Headers (and Customers)
        logger.info("Ingesting Sales Order Headers...")
        for row in iter_jsonl(DATA_DIR / "sales_order_headers"):
            so_id = row.get("salesOrder")
            customer_id = row.get("soldToParty")
            
            query = """
            MERGE (c:Customer {id: $customer_id})
            MERGE (s:SalesOrder {id: $so_id})
            SET s += $props
            MERGE (c)-[:PLACED]->(s)
            """
            session.run(query, customer_id=customer_id, so_id=so_id, props=flatten_props(row))

        # 4. Sales Order Items (and Products)
        logger.info("Ingesting Sales Order Items (Products)...")
        for row in iter_jsonl(DATA_DIR / "sales_order_items"):
            so_id = row.get("salesOrder")
            material = row.get("material")
            net_amount = row.get("netAmount")
            
            query = """
            MATCH (s:SalesOrder {id: $so_id})
            MERGE (p:Product {id: $material})
            MERGE (s)-[:INCLUDES {amount: toFloat($net_amount)}]->(p)
            """
            session.run(query, so_id=so_id, material=material, net_amount=net_amount)

        # 5. Outbound Delivery Items (links Delivery to Sales Order)
        logger.info("Ingesting Outbound Deliveries...")
        for row in iter_jsonl(DATA_DIR / "outbound_delivery_items"):
            del_id = row.get("deliveryDocument")
            ref_so_id = row.get("referenceSdDocument")
            
            # Note: Outbound deliveries reference Sales Orders
            query = """
            MATCH (s:SalesOrder {id: $ref_so_id})
            MERGE (d:Delivery {id: $del_id})
            MERGE (s)-[:HAS_DELIVERY]->(d)
            """
            session.run(query, ref_so_id=ref_so_id, del_id=del_id)

        # 6. Billing Document Headers (links Billing to Customer and JournalEntry)
        logger.info("Ingesting Billing Document Headers...")
        for row in iter_jsonl(DATA_DIR / "billing_document_headers"):
            bill_id = row.get("billingDocument")
            customer_id = row.get("soldToParty")
            accounting_doc = row.get("accountingDocument")
            
            query = """
            MATCH (c:Customer {id: $customer_id})
            MERGE (b:BillingDocument {id: $bill_id})
            SET b += $props
            MERGE (c)-[:HAS_BILLING]->(b)
            WITH b
            OPTIONAL MATCH (j:JournalEntry {id: $accounting_doc})
            FOREACH (x in CASE WHEN j IS NOT NULL THEN [1] ELSE [] END | MERGE (b)-[:HAS_JOURNAL_ENTRY]->(j))
            """
            session.run(query, customer_id=customer_id, bill_id=bill_id, accounting_doc=accounting_doc, props=flatten_props(row))

        # 7. Billing Document Items (links Billing to Delivery or Sales Order)
        logger.info("Ingesting Billing Documents...")
        for row in iter_jsonl(DATA_DIR / "billing_document_items"):
            bill_id = row.get("billingDocument")
            ref_doc = row.get("referenceSdDocument")
            net_amount = row.get("netAmount")
            
            # The reference could be a Delivery or a Sales Order
            query = """
            MERGE (b:BillingDocument {id: $bill_id})
            SET b.netAmount = toFloat($net_amount)
            WITH b
            OPTIONAL MATCH (d:Delivery {id: $ref_doc})
            FOREACH (x in CASE WHEN d IS NOT NULL THEN [1] ELSE [] END | MERGE (d)-[:HAS_BILLING]->(b))
            WITH b, d
            OPTIONAL MATCH (s:SalesOrder {id: $ref_doc})
            FOREACH (x in CASE WHEN s IS NOT NULL THEN [1] ELSE [] END | MERGE (s)-[:HAS_BILLING]->(b))
            """
            session.run(query, bill_id=bill_id, ref_doc=ref_doc, net_amount=net_amount)

        # 8. Journal Entries (links Journal Entry to Billing Document and Customer)
        logger.info("Ingesting Journal Entries...")
        for row in iter_jsonl(DATA_DIR / "journal_entry_items_accounts_receivable"):
            je_id = row.get("accountingDocument")
            ref_bill_id = row.get("referenceDocument")
            customer_id = row.get("customer")
            
            query = """
            OPTIONAL MATCH (b:BillingDocument {id: $ref_bill_id})
            OPTIONAL MATCH (c:Customer {id: $customer_id})
            MERGE (j:JournalEntry {id: $je_id})
            SET j += $props
            FOREACH (x in CASE WHEN b IS NOT NULL THEN [1] ELSE [] END | MERGE (b)-[:HAS_JOURNAL_ENTRY]->(j))
            FOREACH (x in CASE WHEN c IS NOT NULL THEN [1] ELSE [] END | MERGE (c)-[:HAS_JOURNAL_ENTRY]->(j))
            """
            session.run(query, je_id=je_id, ref_bill_id=ref_bill_id, customer_id=customer_id, props=flatten_props(row))

        # 9. Payments (links Payment to Journal Entry)
        logger.info("Ingesting Payments...")
        for row in iter_jsonl(DATA_DIR / "payments_accounts_receivable"):
            je_id = row.get("accountingDocument")
            payment_id = row.get("clearingAccountingDocument")
            
            if payment_id and str(payment_id).strip() and payment_id != "0":
                query = """
                MATCH (j:JournalEntry {id: $je_id})
                MERGE (p:Payment {id: $payment_id})
                MERGE (j)-[:CLEARED_BY_PAYMENT]->(p)
                """
                session.run(query, je_id=je_id, payment_id=payment_id)

    driver.close()
    logger.info("Ingestion complete!")

if __name__ == "__main__":
    run_ingestion()
