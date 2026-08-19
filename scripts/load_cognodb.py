import csv
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "edges.csv"

BATCH_SIZE = 1000


def get_driver():
    load_dotenv()

    uri = os.getenv("COGNODB_URI")
    username = os.getenv("COGNODB_USERNAME")
    password = os.getenv("COGNODB_PASSWORD")

    if not uri or not username or not password:
        raise RuntimeError("CognoDB credentials are missing from .env")

    return GraphDatabase.driver(
        uri,
        auth=(username, password)
    )


def create_constraints(driver):
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS "
            "FOR (u:User) REQUIRE u.id IS UNIQUE"
        ).consume()


def load_batch(tx, rows):
    query = """
    UNWIND $rows AS row
    MERGE (source:User {id: row.source})
    MERGE (target:User {id: row.target})
    MERGE (source)-[:VOTED_FOR]->(target)
    """

    tx.run(query, rows=rows).consume()


def load_data(driver):
    total_relationships = 0
    start_time = time.perf_counter()

    batch = []

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        with driver.session() as session:
            for row in reader:
                batch.append(
                    {
                        "source": int(row["source"]),
                        "target": int(row["target"]),
                    }
                )

                if len(batch) >= BATCH_SIZE:
                    session.execute_write(load_batch, batch)
                    total_relationships += len(batch)

                    print(
                        f"Loaded {total_relationships:,} relationships..."
                    )

                    batch.clear()

            if batch:
                session.execute_write(load_batch, batch)
                total_relationships += len(batch)

    elapsed = time.perf_counter() - start_time

    relationships_per_second = (
        total_relationships / elapsed
        if elapsed > 0
        else 0
    )

    print()
    print("========== LOAD RESULTS ==========")
    print(f"Relationships loaded: {total_relationships:,}")
    print(f"Load time: {elapsed:.2f} seconds")
    print(f"Relationships/second: {relationships_per_second:,.2f}")
    print("==================================")


def main():
    print("Connecting to CognoDB...")

    driver = get_driver()

    try:
        driver.verify_connectivity()

        print("Connected successfully.")

        print("Creating constraint...")
        create_constraints(driver)

        print("Loading dataset...")
        load_data(driver)

    finally:
        driver.close()

    print("Done.")


if __name__ == "__main__":
    main()