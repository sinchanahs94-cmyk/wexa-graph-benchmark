import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "wiki-Vote.txt"
OUTPUT_FILE = PROJECT_ROOT / "data" / "edges.csv"


def prepare_dataset():
    print("Preparing dataset...")

    edges = []

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            source, target = line.split()

            edges.append((int(source), int(target)))

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow(["source", "target"])

        writer.writerows(edges)

    nodes = set()

    for source, target in edges:
        nodes.add(source)
        nodes.add(target)

    print(f"Nodes: {len(nodes):,}")
    print(f"Relationships: {len(edges):,}")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    prepare_dataset()