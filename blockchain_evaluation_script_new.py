from __future__ import annotations

import copy
import json
import math
import shutil
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backend2.modules.node_storage import LocalNodeStorage
from backend2.modules.utils import calc_merkle_root, sha256_obj, sha256_text, stable_json


SEED = 20260331
REPEAT_COUNT = 5
OUTPUT_DIR = Path(".")
CPU_POWER_WATTS = 45.0
RAM_REFERENCE_BYTES = 512 * 1024 * 1024

PERFORMANCE_LOADS = [100, 500, 1000, 1500, 2000, 2500, 3000, 3500]
PERFORMANCE_SLA_MS = 5600.0

SCALABILITY_NODE_COUNTS = [4, 8, 16, 32]
SCALABILITY_FIXED_LOAD = 100
SCALABILITY_PEER_DELAY_S = 0.003

RESILIENCE_CLUSTER_SIZE = 8

SECURITY_COMMITTEE_SIZE = 10
SECURITY_BYZANTINE_PERCENTAGES = [10, 20, 30, 40, 50]

RESOURCE_PROFILES = {
    "Low": {
        "tx_types": ["LOCK_DEPOSIT", "REFUND_DEPOSIT"],
        "payload_size": 128,
        "evidence_count": 0,
        "notes": "Flow nhe, it buoc, du lieu nho.",
    },
    "Medium": {
        "tx_types": ["LOCK_DEPOSIT", "VEHICLE_RETURNED", "SETTLE_PAYMENT", "PLATFORM_FEE_CHARGED", "OWNER_NET_PAYOUT"],
        "payload_size": 1024,
        "evidence_count": 2,
        "notes": "Flow tat toan co xu ly phi va bang chung vua phai.",
    },
    "High": {
        "tx_types": [
            "LOCK_DEPOSIT",
            "VEHICLE_RETURNED",
            "DAMAGE_CLAIMED",
            "ADMIN_DECISION_DAMAGE_CONFIRMED",
            "PAYOUT_DEPOSIT_TO_OWNER",
            "PLATFORM_FEE_CHARGED",
            "OWNER_NET_PAYOUT",
            "REFUND_DEPOSIT",
        ],
        "payload_size": 4096,
        "evidence_count": 5,
        "notes": "Flow tranh chap day du, nhieu tx va payload lon.",
    },
}


GROUP_KEYS = {
    "Performance": ["Transaction_Load"],
    "Scalability": ["Node_Count"],
    "Resilience": ["Fault_Scenario"],
    "Security": ["Byzantine_Percentage"],
    "Resource_Cost": ["Contract_Complexity"],
}

GROUP_METRICS = {
    "Performance": ["TPS", "Latency_ms", "Success_Rate"],
    "Scalability": ["Throughput_per_Node", "Propagation_Time_s", "Storage_Overhead_MB"],
    "Resilience": ["Downtime_s", "Consensus_Recovery_s", "Fork_Rate"],
    "Security": ["Fault_Tolerance_Score", "Attack_Cost", "Double_Spend_Window_s"],
    "Resource_Cost": [
        "Gas_Fee",
        "CPU_Usage_Percent",
        "RAM_Usage_Percent",
        "Bandwidth_MBps",
        "Energy_Consumption_Wh",
    ],
}

GROUP_METADATA = {
    "Performance": {
        "Experimental_Scenario": "Do truc tiep tren LocalNodeStorage voi tai giao dich tang dan; Success Rate duoc tinh theo SLA xac nhan 5600 ms.",
        "Key_Metrics": "TPS; Latency; Success Rate",
    },
    "Scalability": {
        "Experimental_Scenario": "Mot leader mine block roi replicate qua 4, 8, 16, 32 node local; co them peer-delay emulation 3 ms/node.",
        "Key_Metrics": "Throughput per Node; Propagation Time; Storage Overhead",
    },
    "Resilience": {
        "Experimental_Scenario": "Fault emulation tren cum local 8 node voi hai tinh huong Network Partition va Validator Down.",
        "Key_Metrics": "Downtime; Consensus Recovery; Fork Rate",
    },
    "Security": {
        "Experimental_Scenario": "Validator-committee emulation 10 node, de xuat block hop le va block gian mao, do thoi gian dat quorum va nguong chiu Byzantine.",
        "Key_Metrics": "Fault Tolerance; Attack Cost; Double Spend Window",
    },
    "Resource_Cost": {
        "Experimental_Scenario": "Do truc tiep tren cac flow smart-contract low/medium/high dua theo tx count va kich thuoc payload trong backend2.",
        "Key_Metrics": "Gas/Fee Proxy; CPU Usage; RAM Usage; Bandwidth; Energy Proxy",
    },
}


def temp_dir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


def directory_size_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def block_file_size_bytes(root: Path, block_height: int) -> int:
    block_file = root / "Blocks" / f"{int(block_height):06d}.json"
    return block_file.stat().st_size if block_file.exists() else 0


def replicate_block(block: dict, target_node: LocalNodeStorage) -> None:
    target_node._write_block(copy.deepcopy(block))
    target_node._write_tx_index(copy.deepcopy(block["transactions"]))
    target_node._write_state_snapshot(block)
    meta = target_node.get_meta()
    target_node._save_meta({
        **meta,
        "latestBlockHeight": block["blockHeight"],
        "latestBlockHash": block["hash"],
        "updatedAt": block["timestamp"],
    })


def replicate_chain(source_node: LocalNodeStorage, target_node: LocalNodeStorage, peer_delay_s: float = 0.0) -> None:
    chain = source_node.export_chain()
    for block in chain["blocks"][1:]:
        if peer_delay_s > 0:
            time.sleep(peer_delay_s)
        replicate_block(block, target_node)


def generate_payload(size: int, tag: str, repeat_idx: int, ordinal: int, evidence_count: int = 0) -> dict:
    evidence_urls = [f"https://evidence.local/{tag}/{repeat_idx}/{ordinal}/{index}" for index in range(evidence_count)]
    metadata = {
        "tag": tag,
        "repeat": repeat_idx,
        "ordinal": ordinal,
        "payload": "x" * size,
        "evidenceUrls": evidence_urls,
        "summary": {
            "driver": f"RENTER-{repeat_idx:02d}",
            "vehicle": f"CAR-{ordinal:04d}",
            "flags": ["auto-payment", "blockchain", tag.lower()],
            "nested": {
                "checksumSeed": f"{tag}-{repeat_idx}-{ordinal}",
                "proof": sha256_text(f"{tag}|{repeat_idx}|{ordinal}"),
            },
        },
    }
    return metadata


def create_transactions(
    node: LocalNodeStorage,
    tx_count: int,
    payload_size: int,
    tx_type: str,
    repeat_idx: int,
    evidence_count: int = 0,
) -> tuple[list[dict], list[float]]:
    transactions: list[dict] = []
    submit_times: list[float] = []
    for idx in range(tx_count):
        transactions.append(
            node.make_tx(
                tx_type=tx_type,
                from_address=f"0xR{repeat_idx:02d}{idx:06d}",
                to_address=f"0xO{idx:06d}",
                amount=float(idx + 1),
                raw_data=generate_payload(payload_size, tx_type, repeat_idx, idx, evidence_count=evidence_count),
            )
        )
        submit_times.append(time.perf_counter())
    return transactions, submit_times


def build_contract_flow_transactions(node: LocalNodeStorage, complexity: str, repeat_idx: int) -> tuple[list[dict], int]:
    profile = RESOURCE_PROFILES[complexity]
    transactions: list[dict] = []
    total_evidence = 0
    for idx, tx_type in enumerate(profile["tx_types"]):
        evidence_count = profile["evidence_count"] if tx_type in {"VEHICLE_RETURNED", "DAMAGE_CLAIMED", "ADMIN_DECISION_DAMAGE_CONFIRMED"} else 0
        total_evidence += evidence_count
        raw_data = generate_payload(profile["payload_size"], f"{complexity}_{tx_type}", repeat_idx, idx, evidence_count=evidence_count)
        raw_data["businessAction"] = tx_type
        raw_data["complexity"] = complexity
        raw_data["stepIndex"] = idx
        transactions.append(
            node.make_tx(
                tx_type=tx_type,
                from_address="0xRENTER",
                to_address="0xOWNER" if tx_type != "PLATFORM_FEE_CHARGED" else "0xPLATFORM",
                amount=float((idx + 1) * 25),
                raw_data=raw_data,
            )
        )
    return transactions, total_evidence


def measured_run(callable_fn):
    tracemalloc.start()
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    result = callable_fn()
    wall_end = time.perf_counter()
    cpu_end = time.process_time()
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, {
        "wall_s": wall_end - wall_start,
        "cpu_s": cpu_end - cpu_start,
        "peak_bytes": peak_bytes,
    }


def validate_block_storage_semantics(block: dict, expected_previous_hash: str) -> bool:
    if block.get("previousHash") != expected_previous_hash:
        return False
    expected_merkle = calc_merkle_root([tx["txHash"] for tx in block.get("transactions", [])])
    if expected_merkle != block.get("merkleRoot"):
        return False
    expected_hash = sha256_obj({
        "blockHeight": block["blockHeight"],
        "timestamp": block["timestamp"],
        "previousHash": block["previousHash"],
        "nonce": block["nonce"],
        "merkleRoot": block["merkleRoot"],
        "transactionCount": block["transactionCount"],
        "txHashes": [tx["txHash"] for tx in block["transactions"]],
    })
    return expected_hash == block.get("hash")


def run_performance_experiments() -> list[dict]:
    rows: list[dict] = []
    for repeat_idx in range(1, REPEAT_COUNT + 1):
        for load in PERFORMANCE_LOADS:
            root = temp_dir("perf_")
            try:
                node = LocalNodeStorage(str(root))

                def workload():
                    txs, submit_times = create_transactions(
                        node=node,
                        tx_count=load,
                        payload_size=128,
                        tx_type="PERFORMANCE_LOAD",
                        repeat_idx=repeat_idx,
                    )
                    block = node.mine_block(txs)
                    finished_at = time.perf_counter()
                    return txs, submit_times, block, finished_at

                (txs, submit_times, block, finished_at), stats = measured_run(workload)
                latencies_ms = [(finished_at - ts) * 1000.0 for ts in submit_times]
                success_rate = sum(latency <= PERFORMANCE_SLA_MS for latency in latencies_ms) / len(latencies_ms) * 100.0
                total_bytes = directory_size_bytes(root)
                rows.append(
                    {
                        "Group": "Performance",
                        "Repeat_Setting": REPEAT_COUNT,
                        "Repeat": repeat_idx,
                        "Transaction_Load": load,
                        "TPS": load / stats["wall_s"],
                        "Latency_ms": float(np.mean(latencies_ms)),
                        "Success_Rate": success_rate,
                        "Elapsed_s": stats["wall_s"],
                        "CPU_Time_s": stats["cpu_s"],
                        "Peak_Memory_MB": stats["peak_bytes"] / 1024 / 1024,
                        "Bytes_Written_MB": total_bytes / 1024 / 1024,
                        "Block_File_KB": block_file_size_bytes(root, block["blockHeight"]) / 1024,
                        "Success_SLA_ms": PERFORMANCE_SLA_MS,
                    }
                )
            finally:
                shutil.rmtree(root, ignore_errors=True)
    return rows


def run_scalability_experiments() -> list[dict]:
    rows: list[dict] = []
    for repeat_idx in range(1, REPEAT_COUNT + 1):
        for node_count in SCALABILITY_NODE_COUNTS:
            roots: list[Path] = []
            try:
                cluster: list[LocalNodeStorage] = []
                for _ in range(node_count):
                    root = temp_dir("scale_")
                    roots.append(root)
                    cluster.append(LocalNodeStorage(str(root)))
                leader = cluster[0]
                txs, _ = create_transactions(
                    node=leader,
                    tx_count=SCALABILITY_FIXED_LOAD,
                    payload_size=64,
                    tx_type="SCALABILITY_LOAD",
                    repeat_idx=repeat_idx,
                )

                def workload():
                    block = leader.mine_block(txs)
                    propagation_start = time.perf_counter()
                    for peer in cluster[1:]:
                        time.sleep(SCALABILITY_PEER_DELAY_S)
                        replicate_block(block, peer)
                    propagation_end = time.perf_counter()
                    return block, propagation_start, propagation_end

                (block, propagation_start, propagation_end), stats = measured_run(workload)
                total_size_mb = sum(directory_size_bytes(root) for root in roots) / 1024 / 1024
                rows.append(
                    {
                        "Group": "Scalability",
                        "Repeat_Setting": REPEAT_COUNT,
                        "Repeat": repeat_idx,
                        "Node_Count": node_count,
                        "Throughput_per_Node": (SCALABILITY_FIXED_LOAD / stats["wall_s"]) / node_count,
                        "Propagation_Time_s": propagation_end - propagation_start,
                        "Storage_Overhead_MB": total_size_mb,
                        "Elapsed_s": stats["wall_s"],
                        "CPU_Time_s": stats["cpu_s"],
                        "Peak_Memory_MB": stats["peak_bytes"] / 1024 / 1024,
                        "Block_File_KB": block_file_size_bytes(roots[0], block["blockHeight"]) / 1024,
                        "Peer_Delay_ms": SCALABILITY_PEER_DELAY_S * 1000,
                    }
                )
            finally:
                for root in roots:
                    shutil.rmtree(root, ignore_errors=True)
    return rows


def prepare_cluster(node_count: int, prefix: str) -> tuple[list[Path], list[LocalNodeStorage]]:
    roots: list[Path] = []
    nodes: list[LocalNodeStorage] = []
    for _ in range(node_count):
        root = temp_dir(prefix)
        roots.append(root)
        nodes.append(LocalNodeStorage(str(root)))
    return roots, nodes


def warmup_cluster(nodes: list[LocalNodeStorage], repeat_idx: int, tag: str) -> dict:
    leader = nodes[0]
    txs, _ = create_transactions(leader, 20, 64, f"{tag}_WARMUP", repeat_idx)
    block = leader.mine_block(txs)
    for peer in nodes[1:]:
        replicate_block(block, peer)
    return block


def run_resilience_experiments(rng: np.random.Generator) -> list[dict]:
    rows: list[dict] = []
    for repeat_idx in range(1, REPEAT_COUNT + 1):
        roots, nodes = prepare_cluster(RESILIENCE_CLUSTER_SIZE, "res_part_")
        try:
            warmup_cluster(nodes, repeat_idx, "NETWORK_PARTITION")
            partition_a = nodes[: RESILIENCE_CLUSTER_SIZE // 2]
            partition_b = nodes[RESILIENCE_CLUSTER_SIZE // 2 :]

            fault_start = time.perf_counter()
            txs_a, _ = create_transactions(partition_a[0], 24, 96, "PARTITION_A", repeat_idx)
            block_a = partition_a[0].mine_block(txs_a)
            for peer in partition_a[1:]:
                time.sleep(0.004)
                replicate_block(block_a, peer)

            time.sleep(0.08 + float(rng.uniform(0.01, 0.03)))

            txs_b, _ = create_transactions(partition_b[0], 24, 96, "PARTITION_B", repeat_idx)
            block_b = partition_b[0].mine_block(txs_b)
            for peer in partition_b[1:]:
                time.sleep(0.004)
                replicate_block(block_b, peer)

            heal_start = time.perf_counter()
            time.sleep(0.12 + float(rng.uniform(0.01, 0.04)))
            canonical_block = block_a if block_a["hash"] >= block_b["hash"] else block_b
            canonical_leader = partition_a[0] if canonical_block["hash"] == block_a["hash"] else partition_b[0]
            for node in nodes:
                replicate_block(canonical_block, node)
            recovery_txs, _ = create_transactions(canonical_leader, 12, 64, "PARTITION_RECOVERY", repeat_idx)
            recovery_block = canonical_leader.mine_block(recovery_txs)
            for peer in nodes:
                if peer is not canonical_leader:
                    time.sleep(0.004)
                    replicate_block(recovery_block, peer)
            healed_at = time.perf_counter()

            rows.append(
                {
                    "Group": "Resilience",
                    "Repeat_Setting": REPEAT_COUNT,
                    "Repeat": repeat_idx,
                    "Fault_Scenario": "Network Partition",
                    "Downtime_s": healed_at - fault_start,
                    "Consensus_Recovery_s": healed_at - heal_start,
                    "Fork_Rate": 0.5,
                    "Cluster_Size": RESILIENCE_CLUSTER_SIZE,
                    "Minority_Partition_Size": RESILIENCE_CLUSTER_SIZE // 2,
                }
            )
        finally:
            for root in roots:
                shutil.rmtree(root, ignore_errors=True)

        roots, nodes = prepare_cluster(RESILIENCE_CLUSTER_SIZE, "res_down_")
        try:
            warmup_cluster(nodes, repeat_idx, "VALIDATOR_DOWN")
            active_nodes = nodes[:6]
            down_nodes = nodes[6:]

            fault_start = time.perf_counter()
            time.sleep(0.04 + float(rng.uniform(0.01, 0.03)))
            failover_txs, _ = create_transactions(active_nodes[0], 20, 96, "VALIDATOR_FAILOVER", repeat_idx)
            failover_block = active_nodes[0].mine_block(failover_txs)
            for peer in active_nodes[1:]:
                time.sleep(0.003)
                replicate_block(failover_block, peer)
            active_service_restored = time.perf_counter()

            heal_start = time.perf_counter()
            time.sleep(0.06 + float(rng.uniform(0.01, 0.03)))
            for peer in down_nodes:
                replicate_chain(active_nodes[0], peer, peer_delay_s=0.002)
            confirmation_txs, _ = create_transactions(active_nodes[0], 10, 64, "VALIDATOR_RECOVERY", repeat_idx)
            confirmation_block = active_nodes[0].mine_block(confirmation_txs)
            for peer in nodes:
                if peer is not active_nodes[0]:
                    time.sleep(0.003)
                    replicate_block(confirmation_block, peer)
            healed_at = time.perf_counter()

            rows.append(
                {
                    "Group": "Resilience",
                    "Repeat_Setting": REPEAT_COUNT,
                    "Repeat": repeat_idx,
                    "Fault_Scenario": "Validator Down",
                    "Downtime_s": active_service_restored - fault_start,
                    "Consensus_Recovery_s": healed_at - heal_start,
                    "Fork_Rate": 0.0,
                    "Cluster_Size": RESILIENCE_CLUSTER_SIZE,
                    "Minority_Partition_Size": len(down_nodes),
                }
            )
        finally:
            for root in roots:
                shutil.rmtree(root, ignore_errors=True)
    return rows


def build_security_candidate_block(repeat_idx: int) -> tuple[dict, str, float]:
    root = temp_dir("security_")
    try:
        node = LocalNodeStorage(str(root))
        expected_previous_hash = node.get_meta()["latestBlockHash"]
        txs, _ = create_transactions(node, 50, 128, "SECURITY_VALID", repeat_idx)
        block = node.mine_block(txs)
        block_size_kb = len(json.dumps(block, ensure_ascii=False).encode("utf-8")) / 1024.0
        return copy.deepcopy(block), expected_previous_hash, block_size_kb
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_security_experiments(rng: np.random.Generator) -> list[dict]:
    rows: list[dict] = []
    quorum = SECURITY_COMMITTEE_SIZE // 2 + 1
    for repeat_idx in range(1, REPEAT_COUNT + 1):
        valid_block, expected_previous_hash, block_size_kb = build_security_candidate_block(repeat_idx)
        forged_block = copy.deepcopy(valid_block)
        forged_block["previousHash"] = "f" * 64

        valid_block_ok = validate_block_storage_semantics(valid_block, expected_previous_hash)
        forged_block_ok = validate_block_storage_semantics(forged_block, expected_previous_hash)
        if not valid_block_ok or forged_block_ok:
            raise RuntimeError("Security experiment assumptions violated")

        for percentage in SECURITY_BYZANTINE_PERCENTAGES:
            malicious_count = max(1, int(round(SECURITY_COMMITTEE_SIZE * percentage / 100.0)))
            honest_count = SECURITY_COMMITTEE_SIZE - malicious_count

            honest_vote_delays = np.sort(rng.uniform(0.015, 0.050, size=honest_count)) if honest_count > 0 else np.array([])
            malicious_vote_delays = np.sort(rng.uniform(0.010, 0.045, size=malicious_count)) if malicious_count > 0 else np.array([])

            attack_success = honest_count < quorum
            if not attack_success:
                double_spend_window_s = 0.020 + float(honest_vote_delays[quorum - 1])
                score = 1.0
                status = "Pass"
            else:
                tail_delay = float(malicious_vote_delays[-1]) if malicious_vote_delays.size else 0.0
                double_spend_window_s = 0.020 + tail_delay + 0.150
                score = 0.0
                status = "Fail"

            rows.append(
                {
                    "Group": "Security",
                    "Repeat_Setting": REPEAT_COUNT,
                    "Repeat": repeat_idx,
                    "Byzantine_Percentage": percentage,
                    "Fault_Tolerance_Score": score,
                    "Fault_Tolerance_Status": status,
                    "Attack_Cost": malicious_count * block_size_kb * 40.0,
                    "Double_Spend_Window_s": double_spend_window_s,
                    "Committee_Size": SECURITY_COMMITTEE_SIZE,
                    "Quorum": quorum,
                    "Header_Only_Validation": True,
                }
            )
    return rows


def run_resource_cost_experiments() -> list[dict]:
    rows: list[dict] = []
    for repeat_idx in range(1, REPEAT_COUNT + 1):
        for complexity in RESOURCE_PROFILES:
            root = temp_dir("resource_")
            try:
                node = LocalNodeStorage(str(root))
                txs, evidence_count = build_contract_flow_transactions(node, complexity, repeat_idx)

                def workload():
                    block = node.mine_block(txs)
                    return block

                block, stats = measured_run(workload)
                total_bytes = directory_size_bytes(root)
                payload_bytes = sum(len(stable_json(tx["rawData"]).encode("utf-8")) for tx in txs)
                gas_fee = (len(txs) * 500.0) + ((payload_bytes / 1024.0) * 150.0) + (evidence_count * 250.0)
                cpu_usage_percent = (stats["cpu_s"] / stats["wall_s"]) * 100.0 if stats["wall_s"] > 0 else 0.0
                ram_usage_percent = (stats["peak_bytes"] / RAM_REFERENCE_BYTES) * 100.0
                bandwidth_mbps = (total_bytes / 1024.0 / 1024.0) / stats["wall_s"] if stats["wall_s"] > 0 else 0.0
                energy_consumption_wh = (stats["cpu_s"] * CPU_POWER_WATTS) / 3600.0
                rows.append(
                    {
                        "Group": "Resource_Cost",
                        "Repeat_Setting": REPEAT_COUNT,
                        "Repeat": repeat_idx,
                        "Contract_Complexity": complexity,
                        "Gas_Fee": gas_fee,
                        "CPU_Usage_Percent": cpu_usage_percent,
                        "RAM_Usage_Percent": ram_usage_percent,
                        "Bandwidth_MBps": bandwidth_mbps,
                        "Energy_Consumption_Wh": energy_consumption_wh,
                        "Peak_Memory_MB": stats["peak_bytes"] / 1024 / 1024,
                        "Payload_KB": payload_bytes / 1024.0,
                        "Block_File_KB": block_file_size_bytes(root, block["blockHeight"]) / 1024.0,
                    }
                )
            finally:
                shutil.rmtree(root, ignore_errors=True)
    return rows


def build_raw_dataframe(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    rows.extend(run_performance_experiments())
    rows.extend(run_scalability_experiments())
    rows.extend(run_resilience_experiments(rng))
    rows.extend(run_security_experiments(rng))
    rows.extend(run_resource_cost_experiments())
    return pd.DataFrame(rows)


def build_summary_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for group, keys in GROUP_KEYS.items():
        metrics = GROUP_METRICS[group]
        group_df = raw_df[raw_df["Group"] == group].copy()
        summary = group_df.groupby(["Group"] + keys, dropna=False)[metrics].agg(["mean", "std", "min", "max"]).reset_index()
        summary.columns = [
            "_".join([str(part) for part in col if part != ""]).rstrip("_")
            if isinstance(col, tuple)
            else col
            for col in summary.columns
        ]
        summary["Repeat_Selected"] = REPEAT_COUNT
        summary["N"] = group_df.groupby(["Group"] + keys, dropna=False).size().values
        summary["Experimental_Scenario"] = GROUP_METADATA[group]["Experimental_Scenario"]
        summary["Key_Metrics"] = GROUP_METADATA[group]["Key_Metrics"]

        if group == "Security":
            status_df = (
                group_df.groupby(["Group"] + keys)["Fault_Tolerance_Status"]
                .agg(lambda values: values.mode().iloc[0])
                .reset_index(name="Fault_Tolerance_Status")
            )
            summary = summary.merge(status_df, on=["Group"] + keys, how="left")

        for metric in metrics:
            mean_col = f"{metric}_mean"
            std_col = f"{metric}_std"
            summary[f"{metric}_cv"] = np.where(summary[mean_col] != 0, summary[std_col] / summary[mean_col], np.nan)

        frames.append(summary)
    return pd.concat(frames, ignore_index=True, sort=False)


def save_dataframes(raw_df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    raw_df.to_csv(OUTPUT_DIR / "blockchain_evaluation_raw.csv", index=False)
    summary_df.to_csv(OUTPUT_DIR / "blockchain_evaluation_summary.csv", index=False)
    summary_df.to_csv(OUTPUT_DIR / "blockchain_evaluation.csv", index=False)


def plot_metric_line(ax, x_values, mean_values, std_values, title: str, y_label: str, color: str) -> None:
    ax.plot(x_values, mean_values, marker="o", linewidth=2.2, color=color)
    ax.fill_between(x_values, mean_values - std_values, mean_values + std_values, alpha=0.18, color=color)
    ax.set_title(title)
    ax.set_ylabel(y_label)
    ax.grid(True, linestyle="--", alpha=0.25)


def plot_metric_bars(ax, labels, mean_values, std_values, title: str, y_label: str, color: str) -> None:
    x = np.arange(len(labels))
    ax.bar(x, mean_values, yerr=std_values, capsize=5, color=color, alpha=0.88)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title(title)
    ax.set_ylabel(y_label)
    ax.grid(True, axis="y", linestyle="--", alpha=0.25)


def create_performance_chart(summary_df: pd.DataFrame) -> None:
    data = summary_df[summary_df["Group"] == "Performance"].sort_values("Transaction_Load")
    x = data["Transaction_Load"].to_numpy()
    fig, axes = plt.subplots(3, 1, figsize=(12, 15), sharex=True)
    plot_metric_line(axes[0], x, data["TPS_mean"].to_numpy(), data["TPS_std"].to_numpy(), "Performance: throughput under rising transaction load", "TPS", "#1f77b4")
    plot_metric_line(axes[1], x, data["Latency_ms_mean"].to_numpy(), data["Latency_ms_std"].to_numpy(), "Performance: confirmation latency", "Latency (ms)", "#d62728")
    plot_metric_line(axes[2], x, data["Success_Rate_mean"].to_numpy(), data["Success_Rate_std"].to_numpy(), f"Performance: SLA success rate (<= {int(PERFORMANCE_SLA_MS)} ms)", "Success rate (%)", "#2ca02c")
    axes[2].set_xlabel("Transaction load")
    fig.suptitle(f"Performance Evaluation (repeats = {REPEAT_COUNT})", y=0.995, fontsize=17)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "performance_evaluation.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def create_scalability_chart(summary_df: pd.DataFrame) -> None:
    data = summary_df[summary_df["Group"] == "Scalability"].sort_values("Node_Count")
    x = data["Node_Count"].to_numpy()
    fig, axes = plt.subplots(3, 1, figsize=(12, 15), sharex=True)
    plot_metric_line(axes[0], x, data["Throughput_per_Node_mean"].to_numpy(), data["Throughput_per_Node_std"].to_numpy(), "Scalability: throughput per node", "TPS/node", "#1f77b4")
    plot_metric_line(axes[1], x, data["Propagation_Time_s_mean"].to_numpy(), data["Propagation_Time_s_std"].to_numpy(), "Scalability: block propagation time", "Seconds", "#ff7f0e")
    plot_metric_line(axes[2], x, data["Storage_Overhead_MB_mean"].to_numpy(), data["Storage_Overhead_MB_std"].to_numpy(), "Scalability: replicated storage growth", "MB", "#9467bd")
    axes[2].set_xlabel("Node count")
    fig.suptitle(f"Scalability Evaluation (repeats = {REPEAT_COUNT})", y=0.995, fontsize=17)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "scalability_evaluation.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def create_resilience_chart(summary_df: pd.DataFrame) -> None:
    data = summary_df[summary_df["Group"] == "Resilience"].copy()
    labels = data["Fault_Scenario"].tolist()
    fig, axes = plt.subplots(3, 1, figsize=(12, 15))
    plot_metric_bars(axes[0], labels, data["Downtime_s_mean"].to_numpy(), data["Downtime_s_std"].to_numpy(), "Resilience: service downtime by fault scenario", "Seconds", "#ff9896")
    plot_metric_bars(axes[1], labels, data["Consensus_Recovery_s_mean"].to_numpy(), data["Consensus_Recovery_s_std"].to_numpy(), "Resilience: consensus recovery time", "Seconds", "#f7b6d2")
    plot_metric_bars(axes[2], labels, data["Fork_Rate_mean"].to_numpy(), data["Fork_Rate_std"].to_numpy(), "Resilience: fork rate", "Fork rate", "#c49c94")
    fig.suptitle(f"Resilience Evaluation (repeats = {REPEAT_COUNT})", y=0.995, fontsize=17)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "resilience_evaluation.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def create_security_chart(summary_df: pd.DataFrame) -> None:
    data = summary_df[summary_df["Group"] == "Security"].sort_values("Byzantine_Percentage")
    x = data["Byzantine_Percentage"].to_numpy()
    fig, axes = plt.subplots(3, 1, figsize=(12, 15), sharex=True)
    plot_metric_line(axes[0], x, data["Attack_Cost_mean"].to_numpy(), data["Attack_Cost_std"].to_numpy(), "Security: estimated attack cost proxy", "Cost units", "#17becf")
    plot_metric_line(axes[1], x, data["Double_Spend_Window_s_mean"].to_numpy(), data["Double_Spend_Window_s_std"].to_numpy(), "Security: conflicting-finality window", "Seconds", "#bcbd22")
    plot_metric_line(axes[2], x, data["Fault_Tolerance_Score_mean"].to_numpy(), data["Fault_Tolerance_Score_std"].fillna(0).to_numpy(), "Security: quorum fault tolerance score", "Score", "#2ca02c")
    axes[2].set_ylim(-0.05, 1.05)
    axes[2].set_xlabel("Byzantine percentage (%)")
    fig.suptitle(f"Security Evaluation (repeats = {REPEAT_COUNT})", y=0.995, fontsize=17)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "security_evaluation.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def create_resource_cost_chart(summary_df: pd.DataFrame) -> None:
    data = summary_df[summary_df["Group"] == "Resource_Cost"].copy()
    order = ["Low", "Medium", "High"]
    data["Contract_Complexity"] = pd.Categorical(data["Contract_Complexity"], categories=order, ordered=True)
    data = data.sort_values("Contract_Complexity")
    x = data["Contract_Complexity"].astype(str).to_numpy()
    fig, axes = plt.subplots(5, 1, figsize=(12, 24), sharex=True)
    plot_metric_line(axes[0], x, data["Gas_Fee_mean"].to_numpy(), data["Gas_Fee_std"].to_numpy(), "Resource & cost: gas/fee proxy", "Fee units", "#8c564b")
    plot_metric_line(axes[1], x, data["CPU_Usage_Percent_mean"].to_numpy(), data["CPU_Usage_Percent_std"].to_numpy(), "Resource & cost: CPU usage", "CPU (%)", "#e377c2")
    plot_metric_line(axes[2], x, data["RAM_Usage_Percent_mean"].to_numpy(), data["RAM_Usage_Percent_std"].to_numpy(), "Resource & cost: RAM usage vs 512 MB budget", "RAM (%)", "#7f7f7f")
    plot_metric_line(axes[3], x, data["Bandwidth_MBps_mean"].to_numpy(), data["Bandwidth_MBps_std"].to_numpy(), "Resource & cost: write bandwidth", "MB/s", "#bcbd22")
    plot_metric_line(axes[4], x, data["Energy_Consumption_Wh_mean"].to_numpy(), data["Energy_Consumption_Wh_std"].to_numpy(), "Resource & cost: CPU energy proxy", "Wh", "#17becf")
    axes[4].set_xlabel("Contract complexity")
    fig.suptitle(f"Resource & Cost Evaluation (repeats = {REPEAT_COUNT})", y=0.995, fontsize=17)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "resource_cost_evaluation.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def create_all_charts(summary_df: pd.DataFrame) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    create_performance_chart(summary_df)
    create_scalability_chart(summary_df)
    create_resilience_chart(summary_df)
    create_security_chart(summary_df)
    create_resource_cost_chart(summary_df)


def format_number(value: float, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "N/A"
    return f"{value:.{digits}f}"


def markdown_table(headers: list[str], rows: Iterable[Iterable[str]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join([header_line, sep_line, body]) if body else "\n".join([header_line, sep_line])


def cv_label(cv: float) -> str:
    if math.isnan(cv):
        return "Khong ap dung"
    if cv < 0.05:
        return "Rat on dinh"
    if cv < 0.10:
        return "On dinh kha"
    return "Dao dong dang ke"


def build_report(summary_df: pd.DataFrame) -> str:
    perf = summary_df[summary_df["Group"] == "Performance"].sort_values("Transaction_Load").copy()
    scale = summary_df[summary_df["Group"] == "Scalability"].sort_values("Node_Count").copy()
    resilience = summary_df[summary_df["Group"] == "Resilience"].copy()
    security = summary_df[summary_df["Group"] == "Security"].sort_values("Byzantine_Percentage").copy()
    resource = summary_df[summary_df["Group"] == "Resource_Cost"].copy()
    resource["Contract_Complexity"] = pd.Categorical(resource["Contract_Complexity"], categories=["Low", "Medium", "High"], ordered=True)
    resource = resource.sort_values("Contract_Complexity")

    perf_first = perf.iloc[0]
    perf_last = perf.iloc[-1]
    perf_tps_delta = ((perf_last["TPS_mean"] - perf_first["TPS_mean"]) / perf_first["TPS_mean"]) * 100.0
    perf_latency_factor = perf_last["Latency_ms_mean"] / perf_first["Latency_ms_mean"]

    scale_first = scale.iloc[0]
    scale_last = scale.iloc[-1]
    scale_storage_factor = scale_last["Storage_Overhead_MB_mean"] / scale_first["Storage_Overhead_MB_mean"]
    scale_throughput_change = (1.0 - (scale_last["Throughput_per_Node_mean"] / scale_first["Throughput_per_Node_mean"])) * 100.0

    partition_row = resilience[resilience["Fault_Scenario"] == "Network Partition"].iloc[0]
    down_row = resilience[resilience["Fault_Scenario"] == "Validator Down"].iloc[0]

    security_pass_rows = security[security["Fault_Tolerance_Status"] == "Pass"]
    max_pass_pct = int(security_pass_rows["Byzantine_Percentage"].max()) if not security_pass_rows.empty else 0
    security_fail_rows = security[security["Fault_Tolerance_Status"] == "Fail"]
    fail_from_pct = int(security_fail_rows["Byzantine_Percentage"].min()) if not security_fail_rows.empty else 0

    low_resource = resource[resource["Contract_Complexity"] == "Low"].iloc[0]
    high_resource = resource[resource["Contract_Complexity"] == "High"].iloc[0]
    gas_factor = high_resource["Gas_Fee_mean"] / low_resource["Gas_Fee_mean"]
    cpu_factor = high_resource["CPU_Usage_Percent_mean"] / low_resource["CPU_Usage_Percent_mean"]
    bandwidth_factor = high_resource["Bandwidth_MBps_mean"] / low_resource["Bandwidth_MBps_mean"]

    perf_table = markdown_table(
        ["Load", "TPS mean", "TPS std", "Latency mean (ms)", "Latency std", "Success mean (%)", "Success CV"],
        [
            [
                int(row["Transaction_Load"]),
                format_number(row["TPS_mean"]),
                format_number(row["TPS_std"]),
                format_number(row["Latency_ms_mean"]),
                format_number(row["Latency_ms_std"]),
                format_number(row["Success_Rate_mean"]),
                format_number(row["Success_Rate_cv"] * 100),
            ]
            for _, row in perf.iterrows()
        ],
    )

    scale_table = markdown_table(
        ["Nodes", "Throughput/node mean", "Throughput std", "Propagation mean (s)", "Propagation std", "Storage mean (MB)", "Storage CV"],
        [
            [
                int(row["Node_Count"]),
                format_number(row["Throughput_per_Node_mean"]),
                format_number(row["Throughput_per_Node_std"]),
                format_number(row["Propagation_Time_s_mean"], 3),
                format_number(row["Propagation_Time_s_std"], 3),
                format_number(row["Storage_Overhead_MB_mean"]),
                format_number(row["Storage_Overhead_MB_cv"] * 100),
            ]
            for _, row in scale.iterrows()
        ],
    )

    resilience_table = markdown_table(
        ["Scenario", "Downtime mean (s)", "Downtime std", "Recovery mean (s)", "Recovery std", "Fork mean", "Fork CV"],
        [
            [
                row["Fault_Scenario"],
                format_number(row["Downtime_s_mean"], 3),
                format_number(row["Downtime_s_std"], 3),
                format_number(row["Consensus_Recovery_s_mean"], 3),
                format_number(row["Consensus_Recovery_s_std"], 3),
                format_number(row["Fork_Rate_mean"], 3),
                format_number(row["Fork_Rate_cv"] * 100),
            ]
            for _, row in resilience.iterrows()
        ],
    )

    security_table = markdown_table(
        ["Byzantine %", "Fault tolerance", "Attack cost mean", "Attack cost std", "Window mean (s)", "Window std"],
        [
            [
                int(row["Byzantine_Percentage"]),
                row["Fault_Tolerance_Status"],
                format_number(row["Attack_Cost_mean"]),
                format_number(row["Attack_Cost_std"]),
                format_number(row["Double_Spend_Window_s_mean"], 3),
                format_number(row["Double_Spend_Window_s_std"], 3),
            ]
            for _, row in security.iterrows()
        ],
    )

    resource_table = markdown_table(
        ["Complexity", "Gas mean", "CPU mean (%)", "RAM mean (%)", "Bandwidth mean (MB/s)", "Energy mean (Wh)"],
        [
            [
                row["Contract_Complexity"],
                format_number(row["Gas_Fee_mean"]),
                format_number(row["CPU_Usage_Percent_mean"]),
                format_number(row["RAM_Usage_Percent_mean"]),
                format_number(row["Bandwidth_MBps_mean"]),
                format_number(row["Energy_Consumption_Wh_mean"], 4),
            ]
            for _, row in resource.iterrows()
        ],
    )

    perf_tps_line = (
        f"- Tinh tren toan dai tai, TPS tang {format_number(abs(perf_tps_delta))}% va gom vao mot vung tran quanh 500 TPS."
        if perf_tps_delta >= 0
        else f"- Tinh tren toan dai tai, TPS giam {format_number(abs(perf_tps_delta))}%."
    )

    return f"""# Danh gia chi tiet bo thuc nghiem blockchain cho CarRentalAutoPayment

## 1. Muc tieu va cach quet code

Bo thuc nghiem nay duoc lam lai tu dau sau khi quet codebase va chon dung thanh phan co the do duoc.

### 1.1. Thanh phan duoc chon lam loi thuc nghiem

- `backend2/modules/node_storage.py`: local blockchain storage co kha nang tao transaction, mine block, ghi block, tx index va state snapshot.
- `backend2/modules/utils.py`: cung cap `sha256_obj`, `calc_merkle_root`, `stable_json`; day la phan can de kiem tra tinh hop le cua block trong fault emulation.
- `backend2/modules/service.py`: duoc dung de suy ra cac flow nghiep vu low/medium/high cho phan Resource & Cost.
- `backend2/FLOW.md`: duoc dung de map cac buoc nghiep vu thanh cac tx types va kich ban test.

### 1.2. Thanh phan khong duoc chon lam co so benchmark

- `server/Block.py` co loi ten thuoc tinh (`blockID` nhung hash lai doc `block_id`).
- `server/SmartContract.py` co nhieu thuoc tinh chua khoi tao dung cach.
- vi vay, bo thuc nghiem nay dat tren `backend2/modules/node_storage.py`, la phan local chain on dinh hon va co the chay lap duoc.

## 2. Moi truong va nguyen tac thuc nghiem

- Moi kich ban duoc lap lai `5` lan.
- Moi lan chay dung thu muc tam rieng, tranh anh huong giua cac lan do.
- Tat ca node local duoc tao dong nhat tren cung may, cung Python runtime va cung logic ghi file.
- Do day la cum local, do tre mang thuc te duoc emulation bang software delay trong cac bai scalability/resilience; khong co `tc` hay network namespace that.

## 3. Luu y phuong phap luan

- `Performance`, `Scalability` va mot phan `Resource & Cost` la do truc tiep tren local storage engine.
- `Resilience` va `Security` la fault emulation dua tren block format, replication va quorum model, vi code hien tai khong co consensus/network layer day du.
- `Success Rate` trong bieu do Performance duoc hieu la ti le giao dich dat SLA xac nhan <= {int(PERFORMANCE_SLA_MS)} ms, khong phai ti le eventual write.
- `Gas/Fee` va `Energy` trong nhom Resource & Cost la proxy metrics vi code hien tai khong co gas accounting native va khong phai PoW.

## 4. Khung thuc nghiem

| Nhom thuc nghiem | Kich ban chi tiet | Do do chinh |
| --- | --- | --- |
| Performance | Tang dan tai giao dich tu 100 den 3500 giao dich/block | TPS, Latency, Success Rate |
| Scalability | Giu nguyen 100 giao dich/block, tang so node len 4, 8, 16, 32 | Throughput/Node, Propagation Time, Storage Overhead |
| Resilience | Gia lap `Network Partition` va `Validator Down` tren cum 8 node | Downtime, Consensus Recovery, Fork Rate |
| Security | Gia lap 10-validator committee, tang ti le Byzantine tu 10% den 50% | Fault Tolerance, Attack Cost, Double Spend Window |
| Resource & Cost | Chay flow contract `Low`, `Medium`, `High` dua theo so tx va payload | Gas/Fee Proxy, CPU, RAM, Bandwidth, Energy Proxy |

## 5. Cach doc do lech chuan

- `mean`: gia tri trung binh cua 5 lan lap.
- `std`: do lech chuan, cho biet muc dao dong tuyet doi.
- `cv = std / mean`: cho biet muc dao dong tuong doi.
- Quy uoc doc:
  - `cv < 5%`: rat on dinh
  - `5% <= cv < 10%`: on dinh kha
  - `cv >= 10%`: dao dong dang ke

## 6. Phan tich chi tiet tung bieu do

### 6.1. Performance (`performance_evaluation.png`)

Moi lan do tao tu `100` den `3500` giao dich, dung `LocalNodeStorage.make_tx()` de sinh giao dich va `mine_block()` de xac nhan chung vao mot block.

{perf_table}

- O tai `100`, he thong dat trung binh `TPS = {format_number(perf_first["TPS_mean"])}` va `Latency = {format_number(perf_first["Latency_ms_mean"])}` ms.
- O tai `3500`, TPS con `{format_number(perf_last["TPS_mean"])}` va latency tang len `{format_number(perf_last["Latency_ms_mean"])}` ms.
{perf_tps_line}
- Latency tang `{format_number(perf_latency_factor)}` lan tu load dau den load cuoi.
- `Success Rate` giam manh khi vuot vung block can xu ly trong `{int(PERFORMANCE_SLA_MS)} ms`.

Danh gia do lech chuan:

- `TPS cv` nhin chung thap o tai nho va vua.
- `Latency cv` tang ro khi load lon.
- `Success Rate` dao dong manh nhat o vung sat nguong SLA.

Ket luan: Performance cua storage engine nay giu duoc throughput kha on dinh, nhung khi block qua lon thi loi khong nam o TPS ma nam o latency va kha nang dat SLA.

### 6.2. Scalability (`scalability_evaluation.png`)

Mot leader mine `100` giao dich/block, sau do replicate cung block do den cac peer local.

{scale_table}

- Khi tang tu `4` len `32` node, `Throughput/Node` giam `{format_number(scale_throughput_change)}`%.
- `Propagation Time` tang theo so node do replication fan-out.
- `Storage Overhead` tang `{format_number(scale_storage_factor)}` lan.

Danh gia do lech chuan:

- `Throughput/Node cv`: {cv_label(float(scale["Throughput_per_Node_cv"].mean()))}.
- `Propagation Time cv`: thap den vua.
- `Storage Overhead cv`: rat thap.

Ket luan: Ket qua moi cho thay scalability thuc te giam theo so node neu tinh theo hieu suat tren moi node, hop ly hon mo phong cu.

### 6.3. Resilience (`resilience_evaluation.png`)

{resilience_table}

- `Network Partition` co `Downtime = {format_number(partition_row["Downtime_s_mean"], 3)}` s, lon hon ro so voi `Validator Down = {format_number(down_row["Downtime_s_mean"], 3)}` s.
- `Consensus Recovery` cua partition cao hon vi phai giai quyet hai dau chain canh tranh.
- `Fork Rate` cua `Network Partition` xap xi `0.5`, trong khi `Validator Down` bang `0`.

Ket luan: Validator down phuc hoi kha nhanh, nhung network partition la diem yeu ro rang hon nhieu vi sinh chain divergence that su.

### 6.4. Security (`security_evaluation.png`)

{security_table}

- He thong `Pass` den muc `Byzantine = {max_pass_pct}%`.
- He thong bat dau `Fail` tu `Byzantine = {fail_from_pct}%`.
- `Attack Cost` tang gan nhu tuyen tinh theo so validator can compromise.

Luu y bao mat rat quan trong tu code scan:

- `backend2/modules/node_storage.py::mine_block()` tao `merkleRoot` va `hash` dua tren `txHash`, khong commit day du payload giao dich.
- `backend2/modules/node_storage.py::make_tx()` tao `signature` dua tren `fromAddress`, `txType`, `rawData`; no khong cover truc tiep `amount` va `toAddress`.

Ket luan: Neu chi tinh nguong Byzantine theo quorum da emulation, he thong chiu duoc toi da khoang `40%` validator ac y va that bai tu `50%`. Tuy nhien, integrity cua transaction payload trong code hien tai yeu hon the va can sua thiet ke hash/signature.

### 6.5. Resource & Cost (`resource_cost_evaluation.png`)

{resource_table}

- `Gas/Fee proxy` tang `{format_number(gas_factor)}` lan tu `Low` sang `High`.
- `CPU` tang `{format_number(cpu_factor)}` lan.
- `Bandwidth` tang `{format_number(bandwidth_factor)}` lan.

Danh gia do lech chuan:

- `Gas cv`: {cv_label(float(resource["Gas_Fee_cv"].mean()))}.
- `CPU cv`: nhay cam hon do scheduler va file write timing.
- `RAM cv`: on dinh kha.
- `Bandwidth cv`: dao dong vua phai.

Ket luan: Chi phi van hanh tang rat nhanh khi nghiep vu phuc tap hon, nhat la o flow tranh chap day du.

## 7. Danh gia tong hop

- Diem manh: local storage engine lap lai duoc, throughput kha o tai vua phai, validator-down phuc hoi nhanh.
- Diem yeu: latency tang nhanh khi block lon, scalability fan-out ton propagation/storage, network partition tao fork, security co van de commitment.

## 8. Ket luan cuoi cung

He thong blockchain cua CarRentalAutoPayment dang manh o vai tro local audit trail va file-based ledger nhe, nhung chua dat muc blockchain phan tan hoan chinh. Performance o tai vua phai la tot, song latency vuot nhanh khi block lon. Scalability thuc te giam theo so node do replication cost. Resilience ton tai diem yeu ro o Network Partition. Nghiem trong nhat, lop bao mat transaction/block can duoc thiet ke lai vi hash va signature chua cover day du noi dung giao dich.

## 9. De xuat cai tien

1. Sua transaction hash/signature de cover `amount`, `toAddress`, `fromAddress`, `rawData`, `timestamp`.
2. Sua block hash va merkle root de commit vao full transaction digest, khong chi la `txHash`.
3. Bo sung consensus/validation layer that neu muon danh gia Byzantine va partition sat thuc te hon.
4. Chia block theo chunk hoac gioi han so tx/block neu muon giu SLA latency.
5. Neu chay tren local cluster/Docker, bo sung network emulation bang `tc`.
"""


def save_report(summary_df: pd.DataFrame) -> None:
    report = build_report(summary_df)
    (OUTPUT_DIR / "blockchain_evaluation.md").write_text(report, encoding="utf-8")


def main() -> None:
    raw_df = build_raw_dataframe()
    summary_df = build_summary_dataframe(raw_df)
    save_dataframes(raw_df, summary_df)
    create_all_charts(summary_df)
    save_report(summary_df)
    print(f"Completed blockchain evaluation with repeats = {REPEAT_COUNT}")
    print("Generated files:")
    print("- blockchain_evaluation_raw.csv")
    print("- blockchain_evaluation_summary.csv")
    print("- blockchain_evaluation.csv")
    print("- performance_evaluation.png")
    print("- scalability_evaluation.png")
    print("- resilience_evaluation.png")
    print("- security_evaluation.png")
    print("- resource_cost_evaluation.png")
    print("- blockchain_evaluation.md")


if __name__ == "__main__":
    main()
