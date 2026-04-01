from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from supabase import Client, create_client

from modules.auth import AuthService, extract_bearer_token
from modules.auth_models import LoginRequest, RegisterRequest, WalletNonceRequest, WalletUnlinkRequest, WalletVerifyRequest
from modules.config import NODE_DATA_DIR, SUPABASE_KEY, SUPABASE_URL
from modules.html_page import HTML_PAGE
from modules.models import (
    AddVehicleRequest,
    AdminConfirmDamageRequest,
    AdminConfirmNoDamageRequest,
    CreateBookingRequest,
    CreateContractRequest,
    CreateDamageClaimRequest,
    ReturnVehicleRequest,
    SettleContractRequest,
)
from modules.node_storage import LocalNodeStorage
from modules.service import RentalAppService

app = FastAPI(title="Car Rental Demo Server", version="1.3.0")
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

if not SUPABASE_URL or not SUPABASE_KEY:
    supabase: Optional[Client] = None
else:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

node_storage = LocalNodeStorage(NODE_DATA_DIR)
service = RentalAppService(supabase, node_storage) if supabase else None
auth_service = AuthService(supabase) if supabase else None


def require_service() -> RentalAppService:
    if service is None:
        raise HTTPException(status_code=500, detail="Thieu SUPABASE_URL hoac SUPABASE_KEY trong .env")
    return service


def require_auth_service() -> AuthService:
    if auth_service is None:
        raise HTTPException(status_code=500, detail="Thieu SUPABASE_URL hoac SUPABASE_KEY trong .env")
    return auth_service


def get_current_user(token: str = Depends(extract_bearer_token)) -> dict:
    return require_auth_service().get_current_user(token)


def require_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    return current_user


def optional_current_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    if not authorization:
        return None
    try:
        return require_auth_service().get_current_user(extract_bearer_token(authorization))
    except Exception:
        return None


def _user_role(current_user: dict) -> str:
    user = current_user["user"]
    return str(user.get("vaitro") or user.get("vaiTro") or "").strip().lower()


def _require_roles(current_user: dict, *roles: str) -> dict:
    role = _user_role(current_user)
    allowed = {item.lower() for item in roles}
    if role not in allowed:
        raise HTTPException(status_code=403, detail=f"Ban can quyen {', '.join(roles)} de thuc hien thao tac nay")
    return current_user


def _is_admin(current_user: dict) -> bool:
    return _user_role(current_user) == "admin"


def _require_same_user_or_admin(current_user: dict, expected_user_id: Optional[str], detail: str):
    if _is_admin(current_user):
        return
    current_id = current_user["user"].get("id")
    if not expected_user_id or current_id != expected_user_id:
        raise HTTPException(status_code=403, detail=detail)


def _require_same_identifier_or_admin(current_user: dict, *, email: Optional[str] = None, phone: Optional[str] = None, detail: str):
    if _is_admin(current_user):
        return
    user = current_user["user"]
    current_email = (user.get("email") or "").strip().lower()
    current_phone = (user.get("sodienthoai") or user.get("soDienThoai") or "").strip()
    if email and current_email and current_email == email.strip().lower():
        return
    if phone and current_phone and current_phone == phone.strip():
        return
    raise HTTPException(status_code=403, detail=detail)


def _require_admin(current_user: dict = Depends(require_active_user)) -> dict:
    return _require_roles(current_user, "admin")


def _filter_overview_for_user(overview: dict, current_user: dict) -> dict:
    if _is_admin(current_user):
        return overview
    user = current_user["user"]
    user_id = user.get("id")
    wallets = [row for row in (overview.get("wallets") or []) if row.get("nguoidungid") == user_id]
    wallet_addresses = {str(row.get("address") or "").lower() for row in wallets}
    vehicles = [row for row in (overview.get("vehicles") or []) if row.get("chuxeid") == user_id]
    vehicle_ids = {row.get("id") for row in vehicles}
    bookings = [row for row in (overview.get("bookings") or []) if row.get("nguoidungid") == user_id or row.get("xeid") in vehicle_ids]
    booking_ids = {row.get("id") for row in bookings}
    contracts = [row for row in (overview.get("contracts") or []) if row.get("nguoithueid") == user_id or row.get("chuxeid") == user_id or row.get("dangkyid") in booking_ids]
    contract_ids = {row.get("id") for row in contracts}
    deposits = [row for row in (overview.get("deposits") or []) if row.get("hopdongthueid") in contract_ids]
    disputes = [row for row in (overview.get("disputes") or []) if row.get("hopdongthueid") in contract_ids]
    damage_reports = [row for row in (overview.get("damageReports") or []) if row.get("hopdongthueid") in contract_ids]
    dispute_ids = {row.get("id") for row in disputes}
    transactions = [
        row for row in (overview.get("transactions") or [])
        if row.get("hopdongthueid") in contract_ids
        or row.get("tranhchapid") in dispute_ids
        or str(row.get("fromaddress") or "").lower() in wallet_addresses
        or str(row.get("toaddress") or "").lower() in wallet_addresses
    ]
    tx_hashes = {row.get("txhash") for row in transactions}
    events = [row for row in (overview.get("events") or []) if row.get("txhash") in tx_hashes]
    return {
        **overview,
        "users": [user],
        "wallets": wallets,
        "vehicles": vehicles,
        "bookings": bookings,
        "contracts": contracts,
        "deposits": deposits,
        "damageReports": damage_reports,
        "disputes": disputes,
        "transactions": transactions,
        "events": events,
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE


@app.get("/home")
def home_redirect():
    return RedirectResponse(url="/frontend/index.html")


@app.get("/test")
def test_redirect():
    return RedirectResponse(url="/frontend/index.html")


@app.post("/auth/register")
def auth_register(req: RegisterRequest):
    try:
        return require_auth_service().register(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/auth/login")
def auth_login(req: LoginRequest):
    try:
        return require_auth_service().login(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/auth/logout")
def auth_logout(token: str = Depends(extract_bearer_token)):
    try:
        return require_auth_service().logout(token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/auth/me")
def auth_me(token: str = Depends(extract_bearer_token)):
    try:
        return require_auth_service().me(token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/auth/wallet/nonce")
def auth_wallet_nonce(req: WalletNonceRequest, current_user: dict = Depends(require_active_user)):
    try:
        return require_auth_service().create_wallet_nonce(current_user["user"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/auth/wallet/verify")
def auth_wallet_verify(req: WalletVerifyRequest, current_user: dict = Depends(require_active_user)):
    try:
        return require_auth_service().verify_wallet(current_user["user"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/auth/wallet/unlink")
def auth_wallet_unlink(req: WalletUnlinkRequest, current_user: dict = Depends(require_active_user)):
    try:
        return require_auth_service().unlink_wallet(current_user["user"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/overview")
def api_overview(current_user: dict = Depends(require_active_user)):
    try:
        return _filter_overview_for_user(require_service().overview(), current_user)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/node/chain")
def api_chain(current_user: dict = Depends(require_active_user)):
    return node_storage.export_chain()


@app.post("/api/node/reconcile")
def api_reconcile_chain(current_user: dict = Depends(_require_admin)):
    try:
        return require_service().reconcile_chain_to_db()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/node/reconcile")
def api_reconcile_chain_get(current_user: dict = Depends(_require_admin)):
    return api_reconcile_chain(current_user)


@app.get("/api/wallets/overview")
def api_wallets_overview(current_user: dict = Depends(_require_admin)):
    try:
        return require_service().wallets_overview()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/finance/summary")
def api_finance_summary(current_user: dict = Depends(_require_admin)):
    try:
        return require_service().finance_summary()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/finance/transactions")
def api_finance_transactions(walletAddress: Optional[str] = None, txType: Optional[str] = None, contractId: Optional[str] = None, disputeId: Optional[str] = None, current_user: dict = Depends(_require_admin)):
    try:
        return require_service().finance_transactions(wallet_address=walletAddress, tx_type=txType, contract_id=contractId, dispute_id=disputeId)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/contracts/{contract_id}/money-flow")
def api_contract_money_flow(contract_id: str, current_user: dict = Depends(require_active_user)):
    try:
        contract = require_service().one("contracts", id=contract_id)
        if not _is_admin(current_user) and current_user["user"].get("id") not in {contract.get("nguoithueid"), contract.get("chuxeid")}:
            raise HTTPException(status_code=403, detail="Ban khong duoc xem money flow cua contract nay")
        return require_service().contract_money_flow(contract_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/vehicles")
def api_add_vehicle(req: AddVehicleRequest, current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        _require_same_identifier_or_admin(current_user, email=req.owneremail, detail="Owner email phai trung voi tai khoan dang dang nhap")
        return require_service().add_vehicle(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/bookings")
def api_create_booking(req: CreateBookingRequest, current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "khach", "admin")
        _require_same_identifier_or_admin(current_user, email=req.renteremail, detail="Renter email phai trung voi tai khoan dang dang nhap")
        return require_service().create_booking(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/from-booking")
def api_create_contract_from_booking(req: CreateContractRequest, current_user: dict = Depends(require_active_user)):
    try:
        booking = require_service().one("bookings", id=req.dangkyid)
        _require_same_user_or_admin(current_user, booking.get("nguoidungid"), "Chi nguoi thue hoac admin moi duoc tao contract tu booking nay")
        return require_service().create_contract_from_booking(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/create")
def api_create_contract(req: CreateContractRequest, current_user: dict = Depends(require_active_user)):
    return api_create_contract_from_booking(req, current_user)


@app.post("/api/contracts/{contract_id}/lock-deposit")
def api_lock_deposit(contract_id: str, current_user: dict = Depends(require_active_user)):
    try:
        contract = require_service().one("contracts", id=contract_id)
        _require_same_user_or_admin(current_user, contract.get("nguoithueid"), "Chi nguoi thue hoac admin moi duoc khoa coc")
        return require_service().lock_deposit(contract_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/return-vehicle")
def api_return_vehicle(contract_id: str, req: ReturnVehicleRequest, current_user: dict = Depends(require_active_user)):
    try:
        contract = require_service().one("contracts", id=contract_id)
        _require_same_user_or_admin(current_user, contract.get("nguoithueid"), "Chi nguoi thue hoac admin moi duoc tra xe")
        if not _is_admin(current_user) and req.nguoitraid != current_user["user"].get("id"):
            raise HTTPException(status_code=403, detail="nguoiTraId phai trung voi tai khoan dang dang nhap")
        return require_service().return_vehicle(contract_id, req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/damage-claim")
def api_damage_claim(contract_id: str, req: CreateDamageClaimRequest, current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        contract = require_service().one("contracts", id=contract_id)
        _require_same_user_or_admin(current_user, contract.get("chuxeid"), "Chi chu xe hoac admin moi duoc tao damage claim")
        if not _is_admin(current_user) and req.ownerid != current_user["user"].get("id"):
            raise HTTPException(status_code=403, detail="ownerId phai trung voi tai khoan dang dang nhap")
        return require_service().create_damage_claim(contract_id, req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/disputes/{dispute_id}/admin-confirm-no-damage")
def api_admin_confirm_no_damage(dispute_id: str, req: AdminConfirmNoDamageRequest, current_user: dict = Depends(_require_admin)):
    try:
        if req.adminid != current_user["user"].get("id"):
            raise HTTPException(status_code=403, detail="adminId phai trung voi tai khoan admin dang dang nhap")
        return require_service().admin_confirm_no_damage(dispute_id, req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/disputes/{dispute_id}/admin-confirm-damage")
def api_admin_confirm_damage(dispute_id: str, req: AdminConfirmDamageRequest, current_user: dict = Depends(_require_admin)):
    try:
        if req.adminid != current_user["user"].get("id"):
            raise HTTPException(status_code=403, detail="adminId phai trung voi tai khoan admin dang dang nhap")
        return require_service().admin_confirm_damage(dispute_id, req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/settle")
def api_settle_contract(contract_id: str, req: SettleContractRequest, current_user: dict = Depends(require_active_user)):
    try:
        contract = require_service().one("contracts", id=contract_id)
        renter_id = contract.get("nguoithueid")
        owner_id = contract.get("chuxeid")
        if not _is_admin(current_user) and current_user["user"].get("id") not in {renter_id, owner_id}:
            raise HTTPException(status_code=403, detail="Chi renter, owner lien quan hoac admin moi duoc tat toan contract")
        return require_service().settle_contract(
            contract_id=contract_id,
            tong_tien_thanh_toan=req.tongtienthanhtoan,
            tong_tien_hoan_lai=req.tongtienhoanlai,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
