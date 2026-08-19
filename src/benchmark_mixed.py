import csv
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_FILE = RESULTS_DIR / "mixed_workload_results.csv"

CONCURRENCY = 10
TOTAL_OPERATIONS = 200
READ_RATIO = 0.70


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
        max_connection_pool_size=CONCURRENCY
    )


def get_node_ids(driver):
    with driver.session() as session:
        result = session.run(
            "MATCH (u:User) RETURN u.id AS id"
        )

        return [record["id"] for record in result]


def read_operation(driver, node_id):
    query = """
    MATCH (u:User {id: $id})
    RETURN u.id AS id
    """

    with driver.session() as session:
        session.run(query, id=node_id).single()


def write_operation(driver, operation_id):
    query = """
    MERGE (w:BenchmarkWrite {id: $id})
    SET w.created_at = timestamp()
    RETURN w.id AS id
    """

    with driver.session() as session:
        session.run(
            query,
            id=operation_id
        ).single()


def execute_operation(driver, node_ids, operation_number):
    start = time.perf_counter()

    is_read = random.random() < READ_RATIO

    if is_read:
        node_id = random.choice(node_ids)
        read_operation(driver, node_id)
        operation_type = "read"
    else:
        write_operation(
            driver,
            operation_number
        )
        operation_type = "write"

    latency_ms = (
        time.perf_counter() - start
    ) * 1000

    return operation_type, latency_ms


def percentile(values, percentile_value):
    values = sorted(values)

    index = (percentile_value / 100) * (len(values) - 1)

    lower = int(index)
    upper = min(
        lower + 1,
        len(values) - 1
    )

    weight = index - lower

    return (
        values[lower]
        + (
            values[upper] - values[lower]
        ) * weight
    )


def cleanup(driver):
    print("Cleaning up temporary benchmark writes...")

    with driver.session() as session:
        session.run(
            "MATCH (w:BenchmarkWrite) DELETE w"
        ).consume()

    print("Cleanup complete.")


def main():
    print("Connecting to CognoDB...")

    driver = get_driver()

    try:
        driver.verify_connectivity()

        node_ids = get_node_ids(driver)

        print(f"Available nodes: {len(node_ids):,}")

        print()
        print("Mixed workload configuration:")
        print(f"Concurrency: {CONCURRENCY}")
        print(f"Total operations: {TOTAL_OPERATIONS}")
        print(f"Read ratio: {READ_RATIO * 100:.0f}%")
        print(
            f"Write ratio: {(1 - READ_RATIO) * 100:.0f}%"
        )

        # Warm-up
        print()
        print("Running warm-up...")

        for i in range(20):
            execute_operation(
                driver,
                node_ids,
                -i - 1
            )

        print("Warm-up complete.")

        print()
        print("Starting concurrent workload...")

        start_time = time.perf_counter()

        results = []

        with ThreadPoolExecutor(
            max_workers=CONCURRENCY
        ) as executor:

            futures = [
                executor.submit(
                    execute_operation,
                    driver,
                    node_ids,
                    i
                )
                for i in range(TOTAL_OPERATIONS)
            ]

            for future in as_completed(futures):
                results.append(
                    future.result()
                )

        elapsed = time.perf_counter() - start_time

        total_operations = len(results)

        throughput = (
            total_operations / elapsed
            if elapsed > 0
            else 0
        )

        read_latencies = [
            latency
            for operation, latency in results
            if operation == "read"
        ]

        write_latencies = [
            latency
            for operation, latency in results
            if operation == "write"
        ]

        actual_reads = len(read_latencies)
        actual_writes = len(write_latencies)

        print()
        print("=" * 60)
        print("MIXED WORKLOAD RESULTS")
        print("=" * 60)

        print(f"Concurrency: {CONCURRENCY}")
        print(f"Total operations: {total_operations}")
        print(f"Elapsed time: {elapsed:.3f} seconds")
        print(f"Throughput: {throughput:.3f} queries/sec")
        print(f"Reads: {actual_reads}")
        print(f"Writes: {actual_writes}")

        if read_latencies:
            print(
                f"Read p50: "
                f"{percentile(read_latencies, 50):.3f} ms"
            )
            print(
                f"Read p95: "
                f"{percentile(read_latencies, 95):.3f} ms"
            )

        if write_latencies:
            print(
                f"Write p50: "
                f"{percentile(write_latencies, 50):.3f} ms"
            )
            print(
                f"Write p95: "
                f"{percentile(write_latencies, 95):.3f} ms"
            )

        RESULTS_DIR.mkdir(exist_ok=True)

        with open(
            RESULTS_FILE,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow(
                [
                    "database",
                    "concurrency",
                    "total_operations",
                    "elapsed_seconds",
                    "throughput_qps",
                    "reads",
                    "writes",
                    "read_p50_ms",
                    "read_p95_ms",
                    "write_p50_ms",
                    "write_p95_ms",
                ]
            )

            writer.writerow(
                [
                    "CognoDB",
                    CONCURRENCY,
                    total_operations,
                    elapsed,
                    throughput,
                    actual_reads,
                    actual_writes,
                    percentile(read_latencies, 50)
                    if read_latencies
                    else "",
                    percentile(read_latencies, 95)
                    if read_latencies
                    else "",
                    percentile(write_latencies, 50)
                    if write_latencies
                    else "",
                    percentile(write_latencies, 95)
                    if write_latencies
                    else "",
                ]
            )

        print()
        print(f"Saved to: {RESULTS_FILE}")

    finally:
        try:
            cleanup(driver)
        finally:
            driver.close()


if __name__ == "__main__":
    main()