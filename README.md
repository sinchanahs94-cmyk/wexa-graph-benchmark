# CognoDB Cloud Graph Database Benchmark

A reproducible benchmark of CognoDB Cloud using the public SNAP Wiki-Vote graph dataset.

This project was created as part of the Wexa.ai Backend Engineer take-home assignment.

> **Important scope note**
>
> The controlled benchmark execution in this repository was completed against CognoDB Cloud. The assignment requested comparison against at least four additional graph database platforms. Due to the time and infrastructure constraints of the take-home environment, equivalent controlled runs against four additional platforms were not completed. No external numbers are presented as if they were measured by this benchmark.
>
> This repository therefore prioritizes reproducibility, transparent methodology, and honest reporting over fabricated cross-platform results.

---

## 1. Executive Summary

This project benchmarks CognoDB Cloud using the Wiki-Vote directed social-network graph.

The benchmark covers:

- Dataset ingestion throughput
- Exact 1-hop traversal
- Exact 2-hop traversal
- Exact 3-hop traversal
- Indexed property lookup
- Filtered lookup
- Aggregation / group-by workload
- Concurrent mixed read/write workload

Each latency workload uses:

- 20 warm-up executions
- 100 measured executions
- p50 and p95 latency reporting

The mixed workload uses:

- 10 concurrent clients
- 200 total operations
- approximately 70% reads / 30% writes

All benchmark results are written to CSV files under `results/`.

---

# 2. Dataset

The benchmark uses the public Stanford SNAP Wiki-Vote dataset:

https://snap.stanford.edu/data/wiki-Vote.html

The dataset represents Wikipedia admin elections.

Dataset size:

| Metric | Value |
|---|---:|
| Nodes | 7,115 |
| Directed relationships | 103,689 |

The local source file is:

```text
data/wiki-Vote.txt