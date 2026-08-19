import csv
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_FILE = RESULTS_DIR / "lookup_results.csv"

WARMUP_RUNS = 20
MEASURED_RUNS = 100


def get_driver():
    load_dotenv()

    uri = os.getenv("COGNODB_URI")
    username = os.getenv("COGNODB_USERNAME")
    password = os.getenv("COGNODB_PASSWORD")

    return GraphDatabase.driver(
        uri,
        auth=(username, password)
    )


def get_node_ids(driver):
    with driver.session() as session:
        result = session.run(
            "MATCH (u:User) RETURN u.id AS id"
        )

        return [record["id"] for record in result]


def percentile(values, percentile_value):
    values = sorted(values)

    index = (percentile_value / 100) * (len(values) - 1)

    lower = int(index)
    upper = min(lower + 1, len(values) - 1)

    weight = index - lower

    return (
        values[lower]
        + (values[upper] - values[lower]) * weight
    )


def run_lookup(driver, node_id, indexed=False):
    if indexed:
        query = """
        MATCH (u:User {id: $id})
        RETURN u.id AS id
        """
    else:
        query = """
        MATCH (u:User)
        WHERE u.id = $id
        RETURN u.id AS id
        """

    start = time.perf_counter()

    with driver.session() as session:
        session.run(
            query,
            id=node_id
        ).single()

    return (time.perf_counter() - start) * 1000


def benchmark(driver, node_ids, indexed):
    name = "indexed_lookup" if indexed else "filtered_lookup"

    print()
    print(f"Benchmarking {name}...")

    # Warm-up
    for _ in range(WARMUP_RUNS):
        node_id = random.choice(node_ids)
        run_lookup(driver, node_id, indexed)

    print(f"Warm-up complete ({WARMUP_RUNS} runs).")

    latencies = []

    for i in range(1, MEASURED_RUNS + 1):
        node_id = random.choice(node_ids)

        latency = run_lookup(
            driver,
            node_id,
            indexed
        )

        latencies.append(latency)

        if i % 20 == 0:
            print(f"Measured {i}/{MEASURED_RUNS}")

    return {
        "workload": name,
        "runs": len(latencies),
        "p50_ms": percentile(latencies, 50),
        "p95_ms": percentile(latencies, 95),
    }


def save_results(results):
    RESULTS_DIR.mkdir(exist_ok=True)

    with open(
        RESULTS_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "database",
                "workload",
                "runs",
                "p50_ms",
                "p95_ms",
            ]
        )

        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    "database": "CognoDB",
                    **result,
                }
            )


def main():
    print("Connecting to CognoDB...")

    driver = get_driver()

    try:
        driver.verify_connectivity()

        node_ids = get_node_ids(driver)

        print(f"Available nodes: {len(node_ids):,}")

        results = []

        # Existing unique constraint makes id indexed.
        results.append(
            benchmark(
                driver,
                node_ids,
                indexed=True
            )
        )

        results.append(
            benchmark(
                driver,
                node_ids,
                indexed=False
            )
        )

    finally:
        driver.close()

    save_results(results)

    print()
    print("=" * 60)
    print("LOOKUP BENCHMARK RESULTS")
    print("=" * 60)

    for result in results:
        print(
            f"{result['workload']} | "
            f"{result['runs']} runs | "
            f"p50={result['p50_ms']:.3f} ms | "
            f"p95={result['p95_ms']:.3f} ms"
        )

    print()
    print(f"Saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()