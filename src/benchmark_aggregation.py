import csv
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_FILE = RESULTS_DIR / "aggregation_results.csv"

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


def run_aggregation(driver):
    query = """
    MATCH (u:User)-[:VOTED_FOR]->()
    RETURN u.id AS user_id, count(*) AS outgoing_votes
    ORDER BY outgoing_votes DESC
    """

    start = time.perf_counter()

    with driver.session() as session:
        result = session.run(query)

        # Consume the entire result so the measured time
        # includes query execution and result retrieval.
        list(result)

    return (time.perf_counter() - start) * 1000


def main():
    print("Connecting to CognoDB...")

    driver = get_driver()

    try:
        driver.verify_connectivity()

        print("Connected.")

        print()
        print("Running aggregation warm-up...")

        for _ in range(WARMUP_RUNS):
            run_aggregation(driver)

        print(f"Warm-up complete ({WARMUP_RUNS} runs).")

        latencies = []

        print()
        print("Measuring aggregation...")

        for i in range(1, MEASURED_RUNS + 1):
            latency = run_aggregation(driver)

            latencies.append(latency)

            if i % 20 == 0:
                print(f"Measured {i}/{MEASURED_RUNS}")

        p50 = percentile(latencies, 50)
        p95 = percentile(latencies, 95)

        print()
        print("=" * 60)
        print("AGGREGATION BENCHMARK")
        print("=" * 60)
        print(f"Runs: {len(latencies)}")
        print(f"p50: {p50:.3f} ms")
        print(f"p95: {p95:.3f} ms")

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

            writer.writerow(
                {
                    "database": "CognoDB",
                    "workload": "group_by_outgoing_votes",
                    "runs": len(latencies),
                    "p50_ms": p50,
                    "p95_ms": p95,
                }
            )

        print()
        print(f"Saved to: {RESULTS_FILE}")

    finally:
        driver.close()


if __name__ == "__main__":
    main()