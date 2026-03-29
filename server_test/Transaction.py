from dataclasses import dataclass, field
from Service.HashService import now_iso, sha256_obj, sha256_text


@dataclass
class Transaction:
    txType: str
    fromAddress: str
    toAddress: str | None
    amount: float
    contractId: str | None = None
    metadata: dict = field(default_factory=dict)

    timestamp: str = field(default_factory=now_iso)
    signature: str | None = None
    status: str = "PENDING"

    blockNumber: int | None = None
    blockHash: str | None = None
    txIndex: int | None = None

    txHash: str = ""

    def __post_init__(self):
        if not self.txHash:
            self.txHash = self.calculate_hash()

    def payload_to_sign(self) -> dict:
        return {
            "txType": self.txType,
            "fromAddress": self.fromAddress,
            "toAddress": self.toAddress,
            "amount": self.amount,
            "contractId": self.contractId,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    def sign(self, secret: str) -> None:
        raw = f"{self.fromAddress}|{secret}|{sha256_obj(self.payload_to_sign())}"
        self.signature = sha256_text(raw)
        self.txHash = self.calculate_hash()

    def calculate_hash(self) -> str:
        return sha256_obj({
            "payload": self.payload_to_sign(),
            "signature": self.signature,
        })

    def to_dict(self) -> dict:
        return {
            "txHash": self.txHash,
            "txType": self.txType,
            "fromAddress": self.fromAddress,
            "toAddress": self.toAddress,
            "amount": self.amount,
            "contractId": self.contractId,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "status": self.status,
            "blockNumber": self.blockNumber,
            "blockHash": self.blockHash,
            "txIndex": self.txIndex,
        }