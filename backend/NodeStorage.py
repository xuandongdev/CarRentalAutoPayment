import json
import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_json(data) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def sha256_obj(data) -> str:
    return sha256_text(stable_json(data))


def calc_merkle_root(tx_ids: List[str]) -> str:
    if not tx_ids:
        return sha256_text("EMPTY")

    hashes = [sha256_text(tx_id) for tx_id in tx_ids]

    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])

        new_hashes = []
        for i in range(0, len(hashes), 2):
            new_hashes.append(sha256_text(hashes[i] + hashes[i + 1]))
        hashes = new_hashes

    return hashes[0]


class LocalNodeStorage:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.blocks_dir = self.root_dir / "Blocks"
        self.meta_file = self.root_dir / "meta.json"

        self.blocks_dir.mkdir(parents=True, exist_ok=True)
        self._init_meta_if_needed()

    def _init_meta_if_needed(self):
        if not self.meta_file.exists():
            genesis_block = {
                "BlockID": 0,
                "timestamp": now_iso(),
                "previousHash": "0" * 64,
                "nonce": 0,
                "merkleRoot": sha256_text("GENESIS"),
                "transactionCount": 0,
                "transactions": [],
            }
            genesis_block["hash"] = sha256_obj(genesis_block)

            self._write_block_file(genesis_block)
            self._save_meta({
                "chainId": "carRentalAutoPayment",
                "latestBlockNumber": 0,
                "latestBlockHash": genesis_block["hash"],
                "createdAt": now_iso(),
            })

    def _save_meta(self, meta: dict):
        self.meta_file.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _load_meta(self) -> dict:
        return json.loads(self.meta_file.read_text(encoding="utf-8"))

    def _write_block_file(self, block: dict):
        file_path = self.blocks_dir / f'{int(block["BlockID"]):06d}.json'
        file_path.write_text(
            json.dumps(block, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def make_tx(
        self,
        loai_giao_dich: str,
        vi_gui: Optional[str],
        vi_nhan: Optional[str],
        so_tien: float,
        du_lieu_goc: Optional[dict] = None,
    ) -> dict:
        payload = {
            "loaiGiaoDich": loai_giao_dich,
            "viGui": vi_gui,
            "viNhan": vi_nhan,
            "soTien": so_tien,
            "thoiGianGiaoDich": now_iso(),
            "duLieuGoc": du_lieu_goc or {},
        }

        payload["maGiaoDich"] = f'TX{uuid4().hex[:12].upper()}'
        payload["maBamDuLieu"] = sha256_obj(payload["duLieuGoc"])
        payload["chuKy"] = sha256_text(payload["maGiaoDich"] + "|" + (vi_gui or "SYSTEM"))
        payload["trangThai"] = "choXacNhan"
        return payload

    def mine_block(self, danh_sach_giao_dich: List[dict]) -> dict:
        meta = self._load_meta()
        so_khoi_moi = meta["latestBlockNumber"] + 1
        ma_bam_khoi_truoc = meta["latestBlockHash"]

        for tx in danh_sach_giao_dich:
            tx["trangThai"] = "daXacNhan"

        goc_merkle = calc_merkle_root([tx["maGiaoDich"] for tx in danh_sach_giao_dich])

        block = {
            "BlockID": so_khoi_moi,
            "timestamp": now_iso(),
            "previousHash": ma_bam_khoi_truoc,
            "nonce": 0,
            "merkleRoot": goc_merkle,
            "transactionCount": len(danh_sach_giao_dich),
            "transactions": danh_sach_giao_dich,
        }
        block["hash"] = sha256_obj(block)

        for idx, tx in enumerate(block["transactions"]):
            tx["BlockID"] = block["BlockID"]
            tx["hash"] = block["hash"]
            tx["txIndex"] = idx

        self._write_block_file(block)

        meta["latestBlockNumber"] = block["BlockID"]
        meta["latestBlockHash"] = block["hash"]
        meta["updatedAt"] = now_iso()
        self._save_meta(meta)

        return block

    def export_chain(self) -> dict:
        meta = self._load_meta()
        blocks = []

        for file_name in sorted(os.listdir(self.blocks_dir)):
            if file_name.endswith(".json"):
                file_path = self.blocks_dir / file_name
                blocks.append(json.loads(file_path.read_text(encoding="utf-8")))

        return {
            "meta": meta,
            "blocks": blocks,
        }
