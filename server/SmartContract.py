from uuid import uuid4

from Transaction import Transaction


class SmartContract:
    def __init__(self, name, code, blockchain=None, wallets=None):
        self.name = name
        self.code = code
        self.blockchain = blockchain
        self.wallets = wallets or {}
        self.contracts = {}
        self.events = []

    def execute(self, *args):
        return {
            "contract": self.name,
            "arguments": args,
            "result": "executed",
        }

    def createRentalContract(self, vehicle_id, renter_address, rental_period, owner_address=None, deposit_amount=0):
        contract_id = str(uuid4())
        self.contracts[contract_id] = {
            "contract_id": contract_id,
            "vehicle_id": vehicle_id,
            "renter_address": renter_address,
            "owner_address": owner_address,
            "rental_period": rental_period,
            "deposit_amount": float(deposit_amount),
            "locked_deposit": 0.0,
            "usage": [],
            "penalties": [],
            "final_charge": 0.0,
            "status": "CREATED",
        }
        self.emitEvent("RENTAL_CONTRACT_CREATED", self.contracts[contract_id])
        return self.contracts[contract_id]

    def activateRentalContract(self, contract_id):
        self.validateStateTransition(contract_id, "ACTIVE")
        self.contracts[contract_id]["status"] = "ACTIVE"
        self.emitEvent("RENTAL_CONTRACT_ACTIVATED", {"contract_id": contract_id})
        return self.contracts[contract_id]

    def lockDeposit(self, contract_id, amount):
        contract = self.contracts[contract_id]
        renter_wallet = self.wallets.get(contract["renter_address"])
        if renter_wallet is None:
            raise ValueError("Renter wallet not found")
        if not renter_wallet.lockFunds(amount):
            raise ValueError("Insufficient available balance to lock deposit")
        contract["locked_deposit"] += float(amount)
        contract["deposit_amount"] = max(contract["deposit_amount"], contract["locked_deposit"])
        self.emitEvent(
            "DEPOSIT_LOCKED",
            {"contract_id": contract_id, "amount": float(amount), "renter": contract["renter_address"]},
        )
        return contract

    def recordUsage(self, contract_id, usage_data):
        contract = self.contracts[contract_id]
        contract["usage"].append(usage_data)
        self.emitEvent("USAGE_RECORDED", {"contract_id": contract_id, "usage_data": usage_data})
        return contract["usage"]

    def calculateRentalFee(self, km, hours, fuel=0, evidence=None):
        base_fee = float(km) * 5000 + float(hours) * 50000
        fuel_fee = float(fuel) * 10000
        evidence_fee = 50000 if evidence else 0
        return base_fee + fuel_fee + evidence_fee

    def calculateFinalCharge(self, contract_id):
        contract = self.contracts[contract_id]
        usage_total = 0.0
        for usage in contract["usage"]:
            usage_total += self.calculateRentalFee(
                usage.get("km", 0),
                usage.get("hours", 0),
                usage.get("fuel", 0),
                usage.get("evidence"),
            )
        penalty_total = sum(penalty["amount"] for penalty in contract["penalties"])
        contract["final_charge"] = usage_total + penalty_total
        return contract["final_charge"]

    def applyPenalties(self, contract_id, penalties):
        contract = self.contracts[contract_id]
        for penalty in penalties:
            contract["penalties"].append(
                {
                    "reason": penalty.get("reason", "UNSPECIFIED"),
                    "amount": float(penalty.get("amount", 0)),
                }
            )
        self.emitEvent("PENALTIES_APPLIED", {"contract_id": contract_id, "penalties": penalties})
        return contract["penalties"]

    def settlePayment(self, contract_id, amount=None):
        contract = self.contracts[contract_id]
        renter_wallet = self.wallets.get(contract["renter_address"])
        owner_wallet = self.wallets.get(contract["owner_address"])
        if renter_wallet is None or owner_wallet is None:
            raise ValueError("Wallet information is incomplete")

        payable_amount = float(amount) if amount is not None else self.calculateFinalCharge(contract_id)
        locked_used = min(contract["locked_deposit"], payable_amount)
        if locked_used > 0:
            renter_wallet.unlockFunds(locked_used)
            renter_wallet.debit(locked_used)
            owner_wallet.credit(locked_used)

        remaining_amount = payable_amount - locked_used
        if remaining_amount > 0:
            if not renter_wallet.debit(remaining_amount):
                raise ValueError("Renter does not have enough balance to settle remaining payment")
            owner_wallet.credit(remaining_amount)

        transaction = Transaction(
            transaction_id=None,
            amount=payable_amount,
            sender=contract["renter_address"],
            receiver=contract["owner_address"],
            tx_type="RENTAL_PAYMENT",
            metadata={"contract_id": contract_id},
        )
        if self.blockchain is not None:
            self.blockchain.addPendingTransaction(transaction)

        contract["locked_deposit"] -= locked_used
        contract["status"] = "SETTLED"
        self.emitEvent("PAYMENT_SETTLED", {"contract_id": contract_id, "amount": payable_amount})
        return transaction

    def refundDeposit(self, contract_id, amount=None):
        contract = self.contracts[contract_id]
        refund_amount = float(amount) if amount is not None else contract["locked_deposit"]
        if refund_amount <= 0:
            return None

        renter_wallet = self.wallets.get(contract["renter_address"])
        if renter_wallet is None:
            raise ValueError("Renter wallet not found")
        if not renter_wallet.unlockFunds(refund_amount):
            raise ValueError("Unable to unlock requested refund amount")

        contract["locked_deposit"] -= refund_amount
        if contract["locked_deposit"] == 0:
            contract["status"] = "COMPLETED"

        transaction = Transaction(
            transaction_id=None,
            amount=refund_amount,
            sender="DEPOSIT_POOL",
            receiver=contract["renter_address"],
            tx_type="DEPOSIT_REFUND",
            metadata={"contract_id": contract_id},
        )
        if self.blockchain is not None:
            self.blockchain.addPendingTransaction(transaction)

        self.emitEvent("DEPOSIT_REFUNDED", {"contract_id": contract_id, "amount": refund_amount})
        return transaction

    def cancelContract(self, contract_id):
        contract = self.contracts[contract_id]
        self.validateStateTransition(contract_id, "CANCELLED")
        if contract["locked_deposit"] > 0:
            self.refundDeposit(contract_id, contract["locked_deposit"])
        contract["status"] = "CANCELLED"
        self.emitEvent("CONTRACT_CANCELLED", {"contract_id": contract_id})
        return contract

    def validateStateTransition(self, contract_id, new_state):
        valid_transitions = {
            "CREATED": {"ACTIVE", "CANCELLED"},
            "ACTIVE": {"SETTLED", "CANCELLED"},
            "SETTLED": {"COMPLETED"},
            "COMPLETED": set(),
            "CANCELLED": set(),
        }
        current_state = self.contracts[contract_id]["status"]
        if new_state not in valid_transitions.get(current_state, set()):
            raise ValueError(f"Invalid state transition from {current_state} to {new_state}")
        return True

    def emitEvent(self, event_name, event_data):
        event = {"event_name": event_name, "event_data": event_data}
        self.events.append(event)
        return event