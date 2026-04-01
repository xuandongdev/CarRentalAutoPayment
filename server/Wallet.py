import hashlib
from uuid import uuid4


class Wallet:
    def __init__(self, address=None, balance=0, private_key=None):
        self.address = address or self._deriveAddress(str(uuid4()))
        self.balance = float(balance)
        self.locked_balance = 0
        self.owner_id = None
        self.role = ""
        
    def __str__(self):
        return (
            f"Wallet(address={self.address}, balance={self.balance}, "
            f"locked_balance={self.locked_balance})"
        )
    
    def _deriveAddress(self, key_material):
        return hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:16]

    def create(self):
        return {
            "address": self.address,
            "balance": self.balance,
            "locked_balance": self.locked_balance,
        }

    def importWallet(self, private_key):
        self.private_key = private_key
        self.address = self._deriveAddress(private_key)
        return self

    def getAddress(self):
        return self.address

    def getBalance(self):
        return self.balance

    def getAvailableBalance(self):
        return self.balance - self.locked_balance

    def lockFunds(self, amount):
        amount = float(amount)
        if amount <= 0 or self.getAvailableBalance() < amount:
            return False
        self.locked_balance += amount
        return True

    def unlockFunds(self, amount):
        amount = float(amount)
        if amount <= 0 or self.locked_balance < amount:
            return False
        self.locked_balance -= amount
        return True

    def debit(self, amount):
        amount = float(amount)
        if amount <= 0 or self.getAvailableBalance() < amount:
            return False
        self.balance -= amount
        return True

    def credit(self, amount):
        amount = float(amount)
        if amount <= 0:
            return False
        self.balance += amount
        return True

    def signTransaction(self, transaction, private_key=None):
        signing_key = private_key or self.private_key
        return transaction.sign(signing_key)