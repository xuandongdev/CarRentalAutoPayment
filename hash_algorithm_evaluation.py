from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


OUTPUT_DIR = Path(".")
BLOCK_COUNT = 50
ROUNDS_PER_BLOCK = 32
HEATMAP_FILE = OUTPUT_DIR / "hash_algorithm_heatmap.png"
CSV_FILE = OUTPUT_DIR / "hash_algorithm_evaluation.csv"

ALGORITHMS = [
    ("md5", "MD5"),
    ("sha1", "SHA-1"),
    ("sha256", "SHA-256"),
    ("sha512", "SHA-512"),
    ("sha3_256", "SHA3-256"),
]


def build_block_payload(block_idx: int) -> bytes:
    """Create a deterministic synthetic block payload with mild size spikes."""
    tx_count = 20 + (block_idx % 11) * 4
    evidence_count = block_idx % 6
    base_kb = 64 + ((block_idx * 37) % 320)
    spike_kb = 256 if block_idx in {3, 16, 23, 43, 49} else 0
    size_kb = base_kb + spike_kb

    block_obj = {
        "block_index": block_idx,
        "timestamp": f"2026-04-01T{block_idx % 24:02d}:{(block_idx * 7) % 60:02d}:00Z",
        "tx_count": tx_count,
        "evidence_count": evidence_count,
        "notes": f"Synthetic benchmark block {block_idx}",
        "payload": ("BLOCKDATA-%02d|" % block_idx) * (size_kb * 64),
    }
    return json.dumps(block_obj, sort_keys=True).encode("utf-8")


def benchmark_hashes() -> tuple[list[int], list[str], np.ndarray]:
    rows: list[int] = []
    matrix: list[list[float]] = []
    labels = [label for _, label in ALGORITHMS]

    for block_idx in range(1, BLOCK_COUNT + 1):
        payload = build_block_payload(block_idx)
        block_times: list[float] = []
        rows.append(block_idx)

        for algo_name, _ in ALGORITHMS:
            digest_fn = getattr(hashlib, algo_name)
            digest_fn(payload).digest()  # warm-up

            started = time.perf_counter()
            for _ in range(ROUNDS_PER_BLOCK):
                digest_fn(payload).digest()
            elapsed = time.perf_counter() - started
            block_times.append(elapsed)

        matrix.append(block_times)

    return rows, labels, np.array(matrix, dtype=float)


def write_csv(block_rows: list[int], algo_labels: list[str], matrix: np.ndarray) -> None:
    with CSV_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Block"] + algo_labels)
        for block_idx, values in zip(block_rows, matrix):
            writer.writerow([block_idx] + [f"{value:.8f}" for value in values])


def render_heatmap(block_rows: list[int], algo_labels: list[str], matrix: np.ndarray) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(8.4, 11))
    image = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")

    ax.set_title("Heatmap so sanh hieu nang cac thuat toan bam\nqua 50 block tien trinh", fontsize=15)
    ax.set_xlabel("Thuat toan bam", fontsize=11)
    ax.set_ylabel("Block thu", fontsize=11)
    ax.set_xticks(np.arange(len(algo_labels)))
    ax.set_xticklabels([label.lower().replace("-", "") for label in algo_labels], fontsize=10)
    ax.set_yticks(np.arange(len(block_rows)))
    ax.set_yticklabels(block_rows, fontsize=8)

    ax.set_xticks(np.arange(-0.5, len(algo_labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(block_rows), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=0.9, alpha=0.7)
    ax.tick_params(which="minor", bottom=False, left=False)

    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.set_label("Thoi gian thuc thi (giay)", rotation=90)

    fig.tight_layout()
    fig.savefig(HEATMAP_FILE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def print_summary(algo_labels: list[str], matrix: np.ndarray) -> None:
    means = matrix.mean(axis=0)
    mins = matrix.min(axis=0)
    maxs = matrix.max(axis=0)

    print("Hash algorithm summary (seconds across 50 blocks):")
    for label, mean_value, min_value, max_value in zip(algo_labels, means, mins, maxs):
        print(
            f"- {label}: mean={mean_value:.6f}, min={min_value:.6f}, max={max_value:.6f}"
        )


def main() -> None:
    block_rows, algo_labels, matrix = benchmark_hashes()
    write_csv(block_rows, algo_labels, matrix)
    render_heatmap(block_rows, algo_labels, matrix)
    print_summary(algo_labels, matrix)
    print(f"Saved {CSV_FILE.name}")
    print(f"Saved {HEATMAP_FILE.name}")


if __name__ == "__main__":
    main()
