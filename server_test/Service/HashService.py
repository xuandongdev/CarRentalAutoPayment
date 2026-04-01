import hashlib
import json
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_dumps(data) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_obj(data) -> str:
    return sha256_text(stable_dumps(data))


def calc_merkle_root(values: list) -> str:
    if not values:
        return sha256_text("EMPTY")

    hashes = []
    for value in values:
        if isinstance(value, str):
            hashes.append(sha256_text(value))
        else:
            hashes.append(sha256_obj(value))

    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])

        new_hashes = []
        for i in range(0, len(hashes), 2):
            new_hashes.append(sha256_text(hashes[i] + hashes[i + 1]))
        hashes = new_hashes

    return hashes[0]