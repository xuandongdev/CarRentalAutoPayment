import json
import os
from Account import AccountState
from Block import Block
from RentalContract import RentalContract
from Transaction import Transaction
from Service.HashService import now_iso


class Blockchain:
    def __init__(self, chainId: str = "carRentalChain"):
        self.chainId = chainId
        self.accounts: dict[str, AccountState] = {}
        self.contracts: dict[str, RentalContract] = {}
        self.pendingTransactions: list[Transaction] = []
        self.chain: list[Block] = [self.create_genesis_block()]

    def create_genesis_block(self) -> Block:
        genesis_tx = Transaction(
            txType="GENESIS",
            fromAddress="SYSTEM",
            toAddress=None,
            amount=0,
            metadata={"message": "Genesis Block"}
        )
        genesis_tx.signature = "GENESIS_SIGNATURE"
        genesis_tx.txHash = genesis_tx.calculate_hash()
        genesis_tx.status = "CONFIRMED"

        block = Block(
            blockNumber=0,
            previousHash="0" * 64,
            transactions=[genesis_tx],
            validatorAddress="SYSTEM"
        )

        genesis_tx.blockNumber = 0
        genesis_tx.blockHash = block.blockHash
        genesis_tx.txIndex = 0
        return block

    def get_latest_block(self) -> Block:
        return self.chain[-1]

    def register_account(self, account: AccountState) -> None:
        if account.address in self.accounts:
            raise ValueError("address da ton tai")
        self.accounts[account.address] = account

    def add_contract(self, contract: RentalContract) -> None:
        if contract.contractId in self.contracts:
            raise ValueError("contractId da ton tai")
        self.contracts[contract.contractId] = contract

    def validate_transaction(self, tx: Transaction) -> None:
        if tx.txType != "GENESIS" and not tx.signature:
            raise ValueError("giao dich chua co chu ky")

        if tx.txType == "DEPOSIT_LOCK":
            sender = self.accounts.get(tx.fromAddress)
            if not sender:
                raise ValueError("khong tim thay tai khoan nguoi gui")
            if sender.balance < tx.amount:
                raise ValueError("khong du so du de khoa coc")

        elif tx.txType == "RENTAL_PAYMENT":
            sender = self.accounts.get(tx.fromAddress)
            receiver = self.accounts.get(tx.toAddress) if tx.toAddress else None
            if not sender or not receiver:
                raise ValueError("thieu tai khoan gui/nhan")
            total_available = sender.balance + sender.lockedBalance
            if total_available < tx.amount:
                raise ValueError("khong du tong so du de thanh toan")

        elif tx.txType == "DEPOSIT_REFUND":
            receiver = self.accounts.get(tx.toAddress) if tx.toAddress else None
            if not receiver:
                raise ValueError("khong tim thay tai khoan nhan hoan coc")

    def add_transaction(self, tx: Transaction) -> None:
        self.validate_transaction(tx)
        self.pendingTransactions.append(tx)

    def _apply_transaction(self, tx: Transaction) -> None:
        contract = self.contracts.get(tx.contractId) if tx.contractId else None

        if tx.txType == "DEPOSIT_LOCK":
            sender = self.accounts[tx.fromAddress]
            sender.lock_funds(tx.amount)

            if contract:
                contract.lockedDeposit += tx.amount
                contract.contractStatus = "ACTIVE"
                contract.updatedAt = now_iso()

        elif tx.txType == "RENTAL_PAYMENT":
            sender = self.accounts[tx.fromAddress]
            receiver = self.accounts[tx.toAddress]

            used_locked = sender.consume_locked_funds(tx.amount)
            remain = tx.amount - used_locked
            if remain > 0:
                sender.debit(remain)

            receiver.credit(tx.amount)

            if contract:
                contract.finalCharge = tx.amount
                contract.contractStatus = "SETTLED"
                contract.updatedAt = now_iso()

        elif tx.txType == "DEPOSIT_REFUND":
            receiver = self.accounts[tx.toAddress]
            receiver.unlock_funds(tx.amount)

            if contract:
                contract.refundAmount = tx.amount
                contract.lockedDeposit = max(contract.lockedDeposit - tx.amount, 0.0)
                contract.contractStatus = "COMPLETED"
                contract.updatedAt = now_iso()

    def mine_pending_transactions(self, validatorAddress: str = "SYSTEM") -> Block | None:
        if not self.pendingTransactions:
            return None

        latest_block = self.get_latest_block()

        block = Block(
            blockNumber=latest_block.blockNumber + 1,
            previousHash=latest_block.blockHash,
            transactions=self.pendingTransactions.copy(),
            validatorAddress=validatorAddress
        )

        for index, tx in enumerate(block.transactions):
            self._apply_transaction(tx)
            tx.status = "CONFIRMED"
            tx.blockNumber = block.blockNumber
            tx.blockHash = block.blockHash
            tx.txIndex = index

        self.chain.append(block)
        self.pendingTransactions.clear()
        return block

    def is_chain_valid(self) -> bool:
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]

            if current_block.previousHash != previous_block.blockHash:
                return False

            if current_block.calculate_merkle_root() != current_block.merkleRoot:
                return False

            if current_block.calculate_hash() != current_block.blockHash:
                return False

        return True

    def to_dict(self) -> dict:
        return {
            "chainId": self.chainId,
            "isValid": self.is_chain_valid(),
            "accounts": [account.to_dict() for account in self.accounts.values()],
            "contracts": [contract.to_dict() for contract in self.contracts.values()],
            "pendingTransactions": [tx.to_dict() for tx in self.pendingTransactions],
            "chain": [block.to_dict() for block in self.chain],
        }

    def export_to_json(self, file_path: str) -> None:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)