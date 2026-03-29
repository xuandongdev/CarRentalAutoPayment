from dataclasses import dataclass, field
from Service.HashService import now_iso, calc_merkle_root, sha256_obj
from Transaction import Transaction


@dataclass
class Block:
    blockNumber: int
    previousHash: str
    transactions: list[Transaction]
    validatorAddress: str = "SYSTEM"
    timestamp: str = field(default_factory=now_iso)
    merkleRoot: str = ""
    blockHash: str = ""

    def __post_init__(self):
        self.merkleRoot = self.calculate_merkle_root()
        self.blockHash = self.calculate_hash()

    def calculate_merkle_root(self) -> str:
        tx_hashes = [tx.txHash for tx in self.transactions]
        return calc_merkle_root(tx_hashes)

    def calculate_hash(self) -> str:
        return sha256_obj({
            "blockNumber": self.blockNumber,
            "previousHash": self.previousHash,
            "timestamp": self.timestamp,
            "validatorAddress": self.validatorAddress,
            "merkleRoot": self.merkleRoot,
            "transactionHashes": [tx.txHash for tx in self.transactions],
        })

    def to_dict(self) -> dict:
        return {
            "blockNumber": self.blockNumber,
            "previousHash": self.previousHash,
            "timestamp": self.timestamp,
            "validatorAddress": self.validatorAddress,
            "merkleRoot": self.merkleRoot,
            "blockHash": self.blockHash,
            "transactions": [tx.to_dict() for tx in self.transactions],
        }