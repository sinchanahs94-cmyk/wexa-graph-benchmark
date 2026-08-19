import csv
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_FILE = RESULTS_DIR / "traversal_results.csv"

WARMUP_RUNS = 20
MEASURED_RUNS = 100


def get_driver():
    load_dotenv()

    uri = os.getenv("COGNODB_URI")
    username = os.getenv("COGNODB_USERNAME")
    password = os.getenv("COGNODB_PASSWORD")

    if not uri or not username or not password:
        raise RuntimeError("CognoDB credentials are missing from .env")

    return GraphDatabase.driver(
        uri,
        auth=(username, password),
        max_connection_lifetime=300,
        connection_timeout=30,
    )


def get_start_nodes(driver):
    with driver.session() as session:
        result = session.run(
            """
            MATCH (u:User)
            RETURN u.id AS id
            """
        )

        return [record["id"] for record in result]


def run_query(driver, start_id, depth):
    # EXACTLY N hops, not 1..N hops.
    query = f"""
    MATCH (start:User {{id: $start_id}})
          -[:VOTED_FOR*{depth}]->
          (target:User)
    RETURN count(DISTINCT target) AS count
    """

    start = time.perf_counter()

    with driver.session() as session:
        record = session.run(
            query,
            start_id=start_id
        ).single()

    elapsed_ms = (time.perf_counter() - start) * 1000

    return elapsed_ms, record["count"]


def percentile(values, percentile_value):
    sorted_values = sorted(values)

    index = (percentile_value / 100) * (len(sorted_values) - 1)

    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)

    weight = index - lower

    return (
        sorted_values[lower]
        + (sorted_values[upper] - sorted_values[lower]) * weight
    )


def benchmark_depth(driver, start_nodes, depth):
    print()
    print(f"Benchmarking EXACT {depth}-hop traversal...")

    # Warm-up
    for _ in range(WARMUP_RUNS):
        node_id = random.choice(start_nodes)

        try:
            run_query(driver, node_id, depth)
        except (ServiceUnavailable, Neo4jError) as error:
            print(f"Warm-up error: {error}")
            return {
                "depth": depth,
                "status": "failed_during_warmup",
                "completed_runs": 0,
                "p50_ms": None,
                "p95_ms": None,
                "error": str(error),
            }

    print(f"Warm-up complete ({WARMUP_RUNS} runs).")

    latencies = []

    for i in range(1, MEASURED_RUNS + 1):
        node_id = random.choice(start_nodes)

        try:
            latency, _ = run_query(
                driver,
                node_id,
                depth
            )

            latencies.append(latency)

        except (ServiceUnavailable, Neo4jError) as error:
            print()
            print(f"3-hop/connection failure after {len(latencies)} runs.")
            print(f"Error: {error}")

            return {
                "depth": depth,
                "status": "connection_failed",
                "completed_runs": len(latencies),
                "p50_ms": (
                    percentile(latencies, 50)
                    if latencies
                    else None
                ),
                "p95_ms": (
                    percentile(latencies, 95)
                    if latencies
                    else None
                ),
                "error": str(error),
            }

        if i % 20 == 0:
            print(f"Measured {i}/{MEASURED_RUNS}")

    return {
        "depth": depth,
        "status": "complete",
        "completed_runs": len(latencies),
        "p50_ms": percentile(latencies, 50),
        "p95_ms": percentile(latencies, 95),
        "error": "",
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
                "depth",
                "status",
                "completed_runs",
                "p50_ms",
                "p95_ms",
                "error",
            ]
        )

        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    "database": "CognoDB",
                    "workload": "exact_hop_traversal",
                    "depth": result["depth"],
                    "status": result["status"],
                    "completed_runs": result["completed_runs"],
                    "p50_ms": result["p50_ms"],
                    "p95_ms": result["p95_ms"],
                    "error": result["error"],
                }
            )

    print()
    print(f"Results saved to: {RESULTS_FILE}")


def main():
    print("Connecting to CognoDB...")

    driver = get_driver()

    results = []

    try:
        driver.verify_connectivity()

        print("Connected.")

        start_nodes = get_start_nodes(driver)

        print(f"Available nodes: {len(start_nodes):,}")

        for depth in [1, 2, 3]:
            result = benchmark_depth(
                driver,
                start_nodes,
                depth
            )

            results.append(result)

            print()
            print(
                f"{depth}-hop | "
                f"status={result['status']} | "
                f"completed={result['completed_runs']} | "
                f"p50={result['p50_ms']} ms | "
                f"p95={result['p95_ms']} ms"
            )

            # If the database connection fails, create a fresh driver.
            if result["status"] == "connection_failed":
                print("Reconnecting before next workload...")

                driver.close()

                time.sleep(3)

                driver = get_driver()
                driver.verify_connectivity()

    finally:
        driver.close()

    save_results(results)

    print()
    print("=" * 60)
    print("TRAVERSAL BENCHMARK SUMMARY")
    print("=" * 60)

    for result in results:
        print(
            f"{result['depth']}-hop | "
            f"{result['status']} | "
            f"{result['completed_runs']} runs | "
            f"p50={result['p50_ms']} ms | "
            f"p95={result['p95_ms']} ms"
        )


if __name__ == "__main__":
    main()