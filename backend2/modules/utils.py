import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_obj(data: Any) -> str:
    return sha256_text(stable_json(data))


def calc_merkle_root(tx_ids: list[str]) -> str:
    if not tx_ids:
        return sha256_text("EMPTY")
    hashes = [sha256_text(x) for x in tx_ids]
    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        hashes = [sha256_text(hashes[i] + hashes[i + 1]) for i in range(0, len(hashes), 2)]
    return hashes[0]


def normalize_non_empty_str(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} khong duoc rong")
    return text
