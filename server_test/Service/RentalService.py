from RentalContract import RentalContract
from Transaction import Transaction
from Blockchain import Blockchain


class RentalService:
    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain

    def create_contract(
        self,
        contract_id: str,
        booking_id: str,
        vehicle_id: str,
        renter_address: str,
        owner_address: str,
        deposit_amount: float
    ) -> RentalContract:
        contract = RentalContract(
            contractId=contract_id,
            bookingId=booking_id,
            vehicleId=vehicle_id,
            renterAddress=renter_address,
            ownerAddress=owner_address,
            depositAmount=deposit_amount,
        )
        self.blockchain.add_contract(contract)
        return contract

    def lock_deposit(self, contract_id: str, secret: str) -> Transaction:
        contract = self.blockchain.contracts[contract_id]

        tx = Transaction(
            txType="DEPOSIT_LOCK",
            fromAddress=contract.renterAddress,
            toAddress="SYSTEM_ESCROW",
            amount=contract.depositAmount,
            contractId=contract.contractId,
            metadata={
                "action": "lockDeposit",
                "vehicleId": contract.vehicleId,
                "bookingId": contract.bookingId,
            },
        )
        tx.sign(secret)
        self.blockchain.add_transaction(tx)
        return tx

    def record_usage(self, contract_id: str, usage_summary: dict) -> RentalContract:
        contract = self.blockchain.contracts[contract_id]
        contract.record_usage(usage_summary)
        return contract

    def settle_contract(
        self,
        contract_id: str,
        renter_secret: str,
        base_price: float,
        overtime_fee: float = 0.0,
        fuel_fee: float = 0.0,
        damage_fee: float = 0.0,
    ) -> list[Transaction]:
        contract = self.blockchain.contracts[contract_id]

        contract.settle(
            base_price=base_price,
            overtime_fee=overtime_fee,
            fuel_fee=fuel_fee,
            damage_fee=damage_fee,
        )

        payment_tx = Transaction(
            txType="RENTAL_PAYMENT",
            fromAddress=contract.renterAddress,
            toAddress=contract.ownerAddress,
            amount=contract.finalCharge,
            contractId=contract.contractId,
            metadata={
                "action": "settlePayment",
                "usageSummaryHash": contract.usageSummaryHash,
            },
        )
        payment_tx.sign(renter_secret)
        self.blockchain.add_transaction(payment_tx)

        created_txs = [payment_tx]

        if contract.refundAmount > 0:
            refund_tx = Transaction(
                txType="DEPOSIT_REFUND",
                fromAddress="SYSTEM_ESCROW",
                toAddress=contract.renterAddress,
                amount=contract.refundAmount,
                contractId=contract.contractId,
                metadata={"action": "refundDeposit"},
            )
            refund_tx.sign("SYSTEM_SECRET")
            self.blockchain.add_transaction(refund_tx)
            created_txs.append(refund_tx)

        return created_txs