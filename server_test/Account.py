from dataclasses import dataclass, field
from Service.HashService import now_iso


@dataclass
class AccountState:
    address: str
    ownerName: str
    role: str
    balance: float = 0.0
    lockedBalance: float = 0.0
    nonce: int = 0
    publicKey: str | None = None
    status: str = "ACTIVE"
    createdAt: str = field(default_factory=now_iso)
    updatedAt: str = field(default_factory=now_iso)

    def credit(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("amount must be >= 0")
        self.balance += amount
        self.updatedAt = now_iso()

    def debit(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("amount must be >= 0")
        if self.balance < amount:
            raise ValueError(f"{self.address} khong du so du")
        self.balance -= amount
        self.updatedAt = now_iso()

    def lock_funds(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("amount must be >= 0")
        if self.balance < amount:
            raise ValueError(f"{self.address} khong du so du de khoa")
        self.balance -= amount
        self.lockedBalance += amount
        self.updatedAt = now_iso()

    def unlock_funds(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("amount must be >= 0")
        if self.lockedBalance < amount:
            raise ValueError(f"{self.address} khong du so du khoa de mo khoa")
        self.lockedBalance -= amount
        self.balance += amount
        self.updatedAt = now_iso()

    def consume_locked_funds(self, amount: float) -> float:
        if amount < 0:
            raise ValueError("amount must be >= 0")
        used = min(self.lockedBalance, amount)
        self.lockedBalance -= used
        self.updatedAt = now_iso()
        return used

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "ownerName": self.ownerName,
            "role": self.role,
            "balance": self.balance,
            "lockedBalance": self.lockedBalance,
            "nonce": self.nonce,
            "publicKey": self.publicKey,
            "status": self.status,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }