import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
NODE_DATA_DIR = os.getenv("NODE_DATA_DIR", "./NodeData")
SYSTEM_ESCROW_ADDRESS = os.getenv("SYSTEM_ESCROW_ADDRESS", "0xSYSTEMESCROW")
PLATFORM_FEE_ADDRESS = os.getenv("PLATFORM_FEE_ADDRESS", "0xPLATFORMFEE")
PLATFORM_FEE_RATE = float(os.getenv("PLATFORM_FEE_RATE", "0.10"))
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-env")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
SIWE_DOMAIN = os.getenv("SIWE_DOMAIN", "127.0.0.1:8000")
SIWE_URI = os.getenv("SIWE_URI", "http://127.0.0.1:8000")

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
    "wallet_auth_challenges": os.getenv("TABLE_WALLET_AUTH_CHALLENGES", "walletauthchallenge"),
    "auth_sessions": os.getenv("TABLE_AUTH_SESSIONS", "authsession"),
}

# Ung dung van dung cac trang thai nghiep vu mo rong, nhung khi ghi DB se map ve gia tri hop le
# theo schema hien tai cua bang hopdongthue / tiencoc / tranhchap.
CONTRACT_STATUS_ALIASES = {
    "khoiTao": {"khoiTao"},
    "choKhoaCoc": {"khoiTao", "choKhoaCoc"},
    "choChuXacNhanGiaoXe": {"khoiTao", "choChuXacNhanGiaoXe"},
    "choKhachNhanXe": {"khoiTao", "choKhachNhanXe"},
    "dangThue": {"dangThue"},
    "choChuXacNhanTraXe": {"dangThue", "choChuXacNhanTraXe"},
    "choTatToan": {"dangThue", "choTatToan"},
    "choKiemTraTraXe": {"dangThue", "choKiemTraTraXe"},
    "dangTranhChap": {"dangThue", "dangTranhChap"},
    "adminXacNhanKhongHuHai": {"hoanThanh", "adminXacNhanKhongHuHai"},
    "adminXacNhanCoHuHai": {"hoanThanh", "adminXacNhanCoHuHai"},
    "hoanThanh": {"hoanThanh"},
}

CONTRACT_STATUS_DB = {
    "khoiTao": "khoiTao",
    "choKhoaCoc": "khoiTao",
    "choChuXacNhanGiaoXe": "khoiTao",
    "choKhachNhanXe": "khoiTao",
    "dangThue": "dangThue",
    "choChuXacNhanTraXe": "dangThue",
    "choTatToan": "dangThue",
    "choKiemTraTraXe": "dangThue",
    "dangTranhChap": "dangThue",
    "adminXacNhanKhongHuHai": "hoanThanh",
    "adminXacNhanCoHuHai": "hoanThanh",
    "hoanThanh": "hoanThanh",
}

DEPOSIT_STATUS_ALIASES = {
    "chuaKhoa": {"chuaKhoa"},
    "daKhoa": {"daKhoa"},
    "tamGiuDoTranhChap": {"daKhoa", "tamGiuDoTranhChap"},
    "daHoan": {"daHoan"},
    "daChuyenChoOwner": {"daTatToan", "daChuyenChoOwner"},
    "daTatToan": {"daTatToan"},
}

DEPOSIT_STATUS_DB = {
    "chuaKhoa": "chuaKhoa",
    "daKhoa": "daKhoa",
    "tamGiuDoTranhChap": "daKhoa",
    "daHoan": "daHoan",
    "daChuyenChoOwner": "daTatToan",
    "daTatToan": "daTatToan",
}

DISPUTE_STATUS_ALIASES = {
    "moiTao": {"dangMo", "moiTao"},
    "choAdminXacMinh": {"dangXuLy", "choAdminXacMinh"},
    "khongCoHuHai": {"daGiaiQuyet", "dongVuViec", "khongCoHuHai"},
    "coHuHai": {"daGiaiQuyet", "dongVuViec", "coHuHai"},
    "daDong": {"dongVuViec", "daDong"},
}

DISPUTE_STATUS_DB = {
    "moiTao": "dangMo",
    "choAdminXacMinh": "dangXuLy",
    "khongCoHuHai": "dongVuViec",
    "coHuHai": "dongVuViec",
    "daDong": "dongVuViec",
}

TX_EVENT_NAMES = {
    "LOCK_DEPOSIT": "lockDeposit",
    "OWNER_HANDOVER_CONFIRMED": "ownerHandoverConfirmed",
    "RENTER_RECEIVE_CONFIRMED": "renterReceiveConfirmed",
    "OWNER_RETURN_CONFIRMED": "ownerReturnConfirmed",
    "SETTLE_PAYMENT": "settlePayment",
    "REFUND_DEPOSIT": "refundDeposit",
    "VEHICLE_RETURNED": "vehicleReturned",
    "DAMAGE_CLAIMED": "damageClaimed",
    "ADMIN_DECISION_NO_DAMAGE": "adminDecisionNoDamage",
    "ADMIN_DECISION_DAMAGE_CONFIRMED": "adminDecisionDamageConfirmed",
    "PAYOUT_DEPOSIT_TO_OWNER": "payoutDepositToOwner",
    "PLATFORM_FEE_CHARGED": "platformFeeCharged",
    "OWNER_NET_PAYOUT": "ownerNetPayout",
    "RENTAL_PAYMENT_GROSS": "rentalPaymentGross",
    "DAMAGE_PAYOUT_GROSS": "damagePayoutGross",
    "ESCROW_LOCK": "escrowLocked",
    "ESCROW_REFUND": "escrowRefunded",
}
