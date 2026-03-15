import hashlib
import json
from datetime import datetime
from uuid import uuid4


class Transaction:
    def __init__(self, transaction_id, amount, sender, receiver, tx_type="TRANSFER", metadata=None):
        self.transaction_id = transaction_id or str(uuid4())
        self.amount = float(amount)
        self.sender = sender
        self.receiver = receiver
        self.tx_type = tx_type
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow().isoformat()
        self.status = "CREATED"
        self.signature = None
        self.block_hash = None
        self.failure_reason = None

    def __str__(self):
        return (
            f"Transaction ID: {self.transaction_id}, Type: {self.tx_type}, Amount: {self.amount}, "
            f"Sender: {self.sender}, Receiver: {self.receiver}, Status: {self.status}"
        )

    def create(self):
        self.status = "CREATED"
        return self

    def calculateHash(self):
        payload = json.dumps(
            {
                "transaction_id": self.transaction_id,
                "amount": self.amount,
                "sender": self.sender,
                "receiver": self.receiver,
                "tx_type": self.tx_type,
                "metadata": self.metadata,
                "timestamp": self.timestamp,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def sign(self, private_key):
        transaction_hash = self.calculateHash()
        self.signature = hashlib.sha256(f"{private_key}:{transaction_hash}".encode("utf-8")).hexdigest()
        return self.signature

    def verifySignature(self, public_key):
        if self.signature is None:
            return False
        expected_signature = hashlib.sha256(
            f"{public_key}:{self.calculateHash()}".encode("utf-8")
        ).hexdigest()
        return self.signature == expected_signature

    def validate(self):
        if self.amount <= 0:
            return False
        if not self.receiver:
            return False
        if self.sender is not None and self.sender == self.receiver:
            return False
        return True

    def markPending(self):
        self.status = "PENDING"
        self.failure_reason = None
        return self

    def markConfirmed(self, block_hash=None):
        self.status = "CONFIRMED"
        self.block_hash = block_hash
        self.failure_reason = None
        return self

    def markFailed(self, reason="Validation failed"):
        self.status = "FAILED"
        self.failure_reason = reason
        return self

    def toLedgerEntry(self):
        return {
            "transaction_id": self.transaction_id,
            "amount": self.amount,
            "sender": self.sender,
            "receiver": self.receiver,
            "tx_type": self.tx_type,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "status": self.status,
            "signature": self.signature,
            "block_hash": self.block_hash,
            "failure_reason": self.failure_reason,
        }