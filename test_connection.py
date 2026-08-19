import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

uri = os.getenv("COGNODB_URI")
username = os.getenv("COGNODB_USERNAME")
password = os.getenv("COGNODB_PASSWORD")

driver = GraphDatabase.driver(
    uri,
    auth=(username, password)
)

driver.verify_connectivity()

with driver.session() as session:
    result = session.run("RETURN 1 AS test")
    record = result.single()

    print("Cypher query result:", record["test"])

driver.close()

print("Successfully connected to CognoDB!")