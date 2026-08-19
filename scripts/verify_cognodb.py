import os

from dotenv import load_dotenv
from neo4j import GraphDatabase


def main():
    load_dotenv()

    uri = os.getenv("COGNODB_URI")
    username = os.getenv("COGNODB_USERNAME")
    password = os.getenv("COGNODB_PASSWORD")

    driver = GraphDatabase.driver(
        uri,
        auth=(username, password)
    )

    try:
        driver.verify_connectivity()

        with driver.session() as session:

            node_result = session.run(
                "MATCH (n:User) RETURN count(n) AS count"
            ).single()

            relationship_result = session.run(
                "MATCH ()-[r:VOTED_FOR]->() RETURN count(r) AS count"
            ).single()

            print("========== COGNODB DATA VERIFICATION ==========")
            print(f"User nodes: {node_result['count']:,}")
            print(
                f"VOTED_FOR relationships: "
                f"{relationship_result['count']:,}"
            )
            print("===============================================")

    finally:
        driver.close()


if __name__ == "__main__":
    main()