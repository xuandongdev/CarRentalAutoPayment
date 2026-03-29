import hashlib
import json
from datetime import datetime
from uuid import uuid4


class Transaction:
    def __init__(self, transaction_id, amount, senderWallet, receiverWallet, type="TRANSFER", metadata=None):
        self.transaction_id = transaction_id or str(uuid4())
        self.contract_id = None
        self.senderWallet = senderWallet
        self.receiverWallet = receiverWallet
        self.amount = float(amount)
        self.tx_type = type
        self.timestamp = datetime.utcnow().isoformat()
        self.status = ""
        self.metadata = metadata or {} # booking_id, vehicle_id
        self.signature = None
        self.public_key = None

    def __str__(self):
        return (
            f"Transaction ID: {self.transaction_id}, Type: {self.type}, Amount: {self.amount}, "
            f"Sender: {self.senderWallet}, Receiver: {self.receiverWallet}, Status: {self.status}"
        )

    def create(self):
        self.status = "CREATED"
        return self

    def calculateHash(self):
        payload = json.dumps(
            {
                "transaction_id": self.transaction_id,
                "amount": self.amount,
                "senderWallet": self.senderWallet,
                "receiverWallet": self.receiverWallet,
                "type": self.type,
                "metadata": self.metadata,
                "timestamp": self.timestamp,
            },
            sort_keys=True,
        )
        self.dataHash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return self.dataHash

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
        if not self.receiverWallet:
            return False
        if self.senderWallet is not None and self.senderWallet == self.receiverWallet:
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
            "type": self.type,
            "senderWallet": self.senderWallet,
            "receiverWallet": self.receiverWallet,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "status": self.status,
            "dataHash": self.dataHash,
            "metadata": self.metadata,
            "block_hash": self.block_hash,
            "failure_reason": self.failure_reason,
        }