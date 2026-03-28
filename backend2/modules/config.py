import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
NODE_DATA_DIR = os.getenv("NODE_DATA_DIR", "./NodeData")
SYSTEM_ESCROW_ADDRESS = os.getenv("SYSTEM_ESCROW_ADDRESS", "0xSYSTEMESCROW")

TABLES = {
    "users": os.getenv("TABLE_USERS", "nguoidung"),
    "wallets": os.getenv("TABLE_WALLETS", "wallet"),
    "vehicles": os.getenv("TABLE_VEHICLES", "xe"),
    "schedules": os.getenv("TABLE_SCHEDULES", "lichtrongxe"),
    "bookings": os.getenv("TABLE_BOOKINGS", "dangky"),
    "contracts": os.getenv("TABLE_CONTRACTS", "hopdongthue"),
    "deposits": os.getenv("TABLE_DEPOSITS", "tiencoc"),
    "damage_reports": os.getenv("TABLE_DAMAGE_REPORTS", "baocaohuhai"),
    "disputes": os.getenv("TABLE_DISPUTES", "tranhchap"),
    "blocks": os.getenv("TABLE_BLOCKS", "block"),
    "transactions": os.getenv("TABLE_TRANSACTIONS", "transaction"),
    "events": os.getenv("TABLE_EVENTS", "event"),
}

CONTRACT_STATUS_ALIASES = {
    "khoiTao": {"khoiTao"},
    "choKhoaCoc": {"choKhoaCoc"},
    "dangThue": {"dangThue"},
    "choKiemTraTraXe": {"choKiemTraTraXe"},
    "dangTranhChap": {"dangTranhChap"},
    "adminXacNhanKhongHuHai": {"adminXacNhanKhongHuHai"},
    "adminXacNhanCoHuHai": {"adminXacNhanCoHuHai"},
    "hoanThanh": {"hoanThanh"},
}

DEPOSIT_STATUS_ALIASES = {
    "chuaKhoa": {"chuaKhoa"},
    "daKhoa": {"daKhoa"},
    "tamGiuDoTranhChap": {"tamGiuDoTranhChap"},
    "daHoan": {"daHoan"},
    "daChuyenChoOwner": {"daChuyenChoOwner"},
    "daTatToan": {"daTatToan"},
}

DISPUTE_STATUS_ALIASES = {
    "moiTao": {"moiTao"},
    "choAdminXacMinh": {"choAdminXacMinh"},
    "khongCoHuHai": {"khongCoHuHai"},
    "coHuHai": {"coHuHai"},
    "daDong": {"daDong"},
}

TX_EVENT_NAMES = {
    "LOCK_DEPOSIT": "lockDeposit",
    "SETTLE_PAYMENT": "settlePayment",
    "REFUND_DEPOSIT": "refundDeposit",
    "VEHICLE_RETURNED": "vehicleReturned",
    "DAMAGE_CLAIMED": "damageClaimed",
    "ADMIN_DECISION_NO_DAMAGE": "adminDecisionNoDamage",
    "ADMIN_DECISION_DAMAGE_CONFIRMED": "adminDecisionDamageConfirmed",
    "PAYOUT_DEPOSIT_TO_OWNER": "payoutDepositToOwner",
}
