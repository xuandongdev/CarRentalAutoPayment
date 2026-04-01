from dataclasses import dataclass, field
from Service.HashService import now_iso, sha256_obj


@dataclass
class RentalContract:
    contractId: str
    bookingId: str
    vehicleId: str
    renterAddress: str
    ownerAddress: str

    depositAmount: float
    lockedDeposit: float = 0.0

    startTime: str | None = None
    endTime: str | None = None
    actualPickupTime: str | None = None
    actualReturnTime: str | None = None

    usageSummary: dict = field(default_factory=dict)
    usageSummaryHash: str | None = None

    overtimeFee: float = 0.0
    fuelFee: float = 0.0
    damageFee: float = 0.0
    penaltyTotal: float = 0.0

    finalCharge: float = 0.0
    refundAmount: float = 0.0
    contractStatus: str = "CREATED"

    createdAt: str = field(default_factory=now_iso)
    updatedAt: str = field(default_factory=now_iso)

    def activate(self) -> None:
        self.contractStatus = "ACTIVE"
        self.updatedAt = now_iso()

    def record_usage(self, usage_summary: dict) -> None:
        self.usageSummary = usage_summary
        self.usageSummaryHash = sha256_obj(usage_summary)
        self.updatedAt = now_iso()

    def settle(self, base_price: float, overtime_fee: float = 0.0,
               fuel_fee: float = 0.0, damage_fee: float = 0.0) -> None:
        self.overtimeFee = overtime_fee
        self.fuelFee = fuel_fee
        self.damageFee = damage_fee
        self.penaltyTotal = overtime_fee + fuel_fee + damage_fee
        self.finalCharge = base_price + self.penaltyTotal
        self.refundAmount = max(self.lockedDeposit - self.finalCharge, 0.0)
        self.updatedAt = now_iso()

    def to_dict(self) -> dict:
        return {
            "contractId": self.contractId,
            "bookingId": self.bookingId,
            "vehicleId": self.vehicleId,
            "renterAddress": self.renterAddress,
            "ownerAddress": self.ownerAddress,
            "depositAmount": self.depositAmount,
            "lockedDeposit": self.lockedDeposit,
            "startTime": self.startTime,
            "endTime": self.endTime,
            "actualPickupTime": self.actualPickupTime,
            "actualReturnTime": self.actualReturnTime,
            "usageSummary": self.usageSummary,
            "usageSummaryHash": self.usageSummaryHash,
            "overtimeFee": self.overtimeFee,
            "fuelFee": self.fuelFee,
            "damageFee": self.damageFee,
            "penaltyTotal": self.penaltyTotal,
            "finalCharge": self.finalCharge,
            "refundAmount": self.refundAmount,
            "contractStatus": self.contractStatus,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }