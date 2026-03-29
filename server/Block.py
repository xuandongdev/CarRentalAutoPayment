import hashlib
import json
from datetime import datetime


class Block:
    def __init__(self, block_id, data=None):
        self.blockID = block_id
        self.previous_hash = ""
        self.timestamp = datetime.utcnow().isoformat()
        self.transactions = []
        self.merkle_root = ""
        self.hash = ""

    def __repr__(self):
        return f"Block(id={self.blockID}, tx_count={len(self.transactions)}, hash={self.hash})"

    def constructor(self, previous_hash="0"):
        self.previous_hash = previous_hash
        self.merkle_root = self.calculateMerkleRoot()
        self.hash = self.calculateHash()
        return self

    def calculateHash(self):
        payload = json.dumps(
            {
                "block_id": self.block_id,
                "previous_hash": self.previous_hash,
                "timestamp": self.timestamp,
                "merkle_root": self.merkle_root,
                "transactions": [tx.calculateHash() for tx in self.transactions],
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def calculateMerkleRoot(self):
        if not self.transactions:
            return hashlib.sha256(b"EMPTY_BLOCK").hexdigest()

        hashes = [tx.calculateHash() for tx in self.transactions]
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256(f"{hashes[index]}{hashes[index + 1]}".encode("utf-8")).hexdigest()
                for index in range(0, len(hashes), 2)
            ]
        return hashes[0]

    def addTransaction(self, transaction):
        if not transaction.validate():
            transaction.markFailed("Invalid transaction")
            return False
        transaction.markPending()
        self.transactions.append(transaction)
        self.data = self.transactions
        return True

    def validateTransactions(self):
        return all(transaction.validate() for transaction in self.transactions)

    def sealBlock(self, previous_hash):
        self.previous_hash = previous_hash
        self.merkle_root = self.calculateMerkleRoot()
        self.hash = self.calculateHash()
        return self.hash

    def isValid(self, previous_hash):
        if self.previous_hash != previous_hash:
            return False
        if not self.validateTransactions():
            return False
        if self.calculateMerkleRoot() != self.merkle_root:
            return False
        return self.calculateHash() == self.hash