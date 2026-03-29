import json
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

from .utils import calc_merkle_root, now_iso, sha256_obj, sha256_text, stable_json


class LocalNodeStorage:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.blocks_dir = self.root_dir / "Blocks"
        self.state_dir = self.root_dir / "State"
        self.transaction_index_dir = self.root_dir / "TransactionIndex"
        self.meta_dir = self.root_dir / "Meta"
        self.meta_file = self.root_dir / "meta.json"

        self.blocks_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.transaction_index_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self._init_meta_if_needed()

    def _init_meta_if_needed(self):
        if self.meta_file.exists():
            return

        genesis = {
            "blockHeight": 0,
            "timestamp": now_iso(),
            "previousHash": "0" * 64,
            "nonce": 0,
            "merkleRoot": sha256_text("GENESIS"),
            "transactionCount": 0,
            "transactions": [],
        }
        genesis["hash"] = sha256_obj(genesis)
        self._write_block(genesis)
        self._save_meta({
            "chainId": "carRentalAutoPayment",
            "latestBlockHeight": 0,
            "latestBlockHash": genesis["hash"],
            "createdAt": now_iso(),
        })

    def _save_meta(self, meta: dict):
        text = json.dumps(meta, ensure_ascii=False, indent=2)
        self.meta_file.write_text(text, encoding="utf-8")
        (self.meta_dir / "latestMeta.json").write_text(text, encoding="utf-8")

    def _load_meta(self) -> dict:
        return json.loads(self.meta_file.read_text(encoding="utf-8"))

    def get_meta(self) -> dict:
        return self._load_meta()

    def sync_head(self, block_height: int, block_hash: str):
        meta = self._load_meta()
        current_height = int(meta.get("latestBlockHeight", 0))
        current_hash = meta.get("latestBlockHash")
        if block_height < current_height:
            return
        if block_height == current_height and block_hash == current_hash:
            return
        self._save_meta({**meta, "latestBlockHeight": int(block_height), "latestBlockHash": block_hash, "updatedAt": now_iso()})

    def _write_block(self, block: dict):
        file_path = self.blocks_dir / f"{int(block['blockHeight']):06d}.json"
        file_path.write_text(json.dumps(block, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_tx_index(self, txs: list[dict]):
        for tx in txs:
            index_path = self.transaction_index_dir / f"{tx['txHash']}.json"
            index_path.write_text(
                json.dumps({
                    "txHash": tx["txHash"],
                    "blockHeight": tx.get("blockHeight"),
                    "blockHash": tx.get("blockHash"),
                    "txIndex": tx.get("txIndex"),
                    "txType": tx.get("txType"),
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def _write_state_snapshot(self, block: dict):
        snapshot = {
            "latestBlockHeight": block["blockHeight"],
            "latestBlockHash": block["hash"],
            "updatedAt": now_iso(),
        }
        (self.state_dir / "latest.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    def make_tx(
        self,
        tx_type: str,
        from_address: Optional[str],
        to_address: Optional[str],
        amount: float,
        raw_data: Optional[dict] = None,
    ) -> dict:
        raw_data = raw_data or {}
        return {
            "txHash": f"TX{uuid4().hex[:12].upper()}",
            "txType": tx_type,
            "dataHash": sha256_obj(raw_data),
            "fromAddress": from_address,
            "toAddress": to_address,
            "amount": float(amount),
            "timestamp": now_iso(),
            "signature": sha256_text((from_address or "SYSTEM") + "|" + tx_type + "|" + stable_json(raw_data)),
            "status": "confirmed",
            "rawData": raw_data,
        }

    def mine_block(self, txs: list[dict]) -> dict:
        meta = self._load_meta()
        block_height = int(meta["latestBlockHeight"]) + 1
        block = {
            "blockHeight": block_height,
            "timestamp": now_iso(),
            "previousHash": meta["latestBlockHash"],
            "nonce": 0,
            "merkleRoot": calc_merkle_root([tx["txHash"] for tx in txs]),
            "transactionCount": len(txs),
            "transactions": txs,
        }
        block["hash"] = sha256_obj({
            "blockHeight": block["blockHeight"],
            "timestamp": block["timestamp"],
            "previousHash": block["previousHash"],
            "nonce": block["nonce"],
            "merkleRoot": block["merkleRoot"],
            "transactionCount": block["transactionCount"],
            "txHashes": [tx["txHash"] for tx in txs],
        })

        for idx, tx in enumerate(block["transactions"]):
            tx["blockHeight"] = block["blockHeight"]
            tx["blockHash"] = block["hash"]
            tx["txIndex"] = idx
            tx["status"] = "confirmed"

        self._write_block(block)
        self._write_tx_index(block["transactions"])
        self._write_state_snapshot(block)
        self._save_meta({**meta, "latestBlockHeight": block_height, "latestBlockHash": block["hash"], "updatedAt": now_iso()})
        return block

    def export_chain(self) -> dict:
        blocks = []
        for file_name in sorted(os.listdir(self.blocks_dir)):
            if file_name.endswith(".json"):
                blocks.append(json.loads((self.blocks_dir / file_name).read_text(encoding="utf-8")))
        return {"meta": self._load_meta(), "blocks": blocks}
