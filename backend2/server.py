from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from supabase import Client, create_client

from modules.auth import AuthService, extract_bearer_token
from modules.auth_models import LoginRequest, RegisterRequest, WalletNonceRequest, WalletUnlinkRequest, WalletVerifyRequest
from modules.config import BOOKING_JOB_SECRET, NODE_DATA_DIR, SUPABASE_KEY, SUPABASE_URL
from modules.html_page import HTML_PAGE
from modules.models import (
    AddVehicleRequest,
    AdminConfirmDamageRequest,
    AdminConfirmNoDamageRequest,
    ApproveBookingRequest,
    ConfirmContractStepRequest,
    CreateAvailabilityRequest,
    CreateBookingRequest,
    CreateContractRequest,
    CreateDamageClaimRequest,
    RejectBookingRequest,
    ResolveExpiredBookingsRequest,
    ReturnVehicleRequest,
    SettleContractRequest,
    UpdateVehicleStatusRequest,
)
from modules.node_storage import LocalNodeStorage
from modules.service import RentalAppService

app = FastAPI(title="Car Rental Demo Server", version="2.0.0")
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
    try:
        return require_auth_service().get_current_user(token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Khong the xac thuc nguoi dung do loi ket noi dich vu: {exc}")


def require_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    return current_user


def optional_current_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    if not authorization:
        return None
    try:
        return require_auth_service().get_current_user(extract_bearer_token(authorization))
    except Exception:
        return None


def _optional_user_payload(current_user: Optional[dict]) -> Optional[dict]:
    if not current_user:
        return None
    return current_user.get("user")


def _require_recent_step_up(
    current_user: dict = Depends(require_active_user),
    step_up_challenge_id: Optional[str] = Header(default=None, alias="X-Step-Up-Challenge-Id"),
) -> dict:
    if not step_up_challenge_id:
        raise HTTPException(
            status_code=403,
            detail="Thieu xac thuc step-up. Vui long ky vi de xac nhan thao tac blockchain nhay cam.",
        )
    try:
        require_auth_service().verify_step_up_assertion(current_user["user"], step_up_challenge_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return current_user


def _user_role(current_user: dict) -> str:
    user = current_user["user"]
    return str(user.get("vaitro") or user.get("vaiTro") or "").strip().lower()


def _dashboard_path_by_role(role: str) -> str:
    if role == "admin":
        return "/admin/dashboard"
    if role == "chuxe":
        return "/owner/dashboard"
    return "/renter/dashboard"


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


def _require_admin(current_user: dict = Depends(require_active_user)) -> dict:
    return _require_roles(current_user, "admin")


def _redirect_frontend(path: str, params: Optional[dict] = None) -> RedirectResponse:
    url = f"/frontend/{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    return RedirectResponse(url=url)


def _guest_only_page(path: str, current_user: Optional[dict]) -> RedirectResponse:
    # Token hien dang duoc luu o localStorage, server khong nhin thay Authorization
    # khi browser GET page route. Vi vay route HTML luon tra ve trang frontend;
    # guest/auth redirect se duoc xu ly o frontend qua /auth/me.
    return _redirect_frontend(path)


def _role_page(path: str, current_user: Optional[dict], *allowed_roles: str) -> RedirectResponse:
    # Xem ghi chu trong _guest_only_page: page guard do frontend dam nhan.
    return _redirect_frontend(path)


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
    return _redirect_frontend("index.html")


@app.get("/home")
def home_redirect():
    return RedirectResponse(url="/")


@app.get("/test")
def test_redirect():
    return RedirectResponse(url="/admin/debug")


@app.get("/legacy", response_class=HTMLResponse)
def legacy_index():
    return HTML_PAGE


@app.get("/login")
def login_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _guest_only_page("login.html", current_user)


@app.get("/register")
def register_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _guest_only_page("register.html", current_user)


@app.get("/vehicles")
def vehicles_page():
    return _redirect_frontend("vehicles.html")


@app.get("/vehicles/{vehicle_id}")
def vehicle_detail_page(vehicle_id: str):
    return _redirect_frontend("vehicle-detail.html", {"id": vehicle_id})


@app.get("/owner/dashboard")
def owner_dashboard_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("owner/dashboard.html", current_user, "chuxe", "admin")


@app.get("/owner/vehicles")
def owner_vehicles_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("owner/vehicles.html", current_user, "chuxe", "admin")


@app.get("/owner/vehicles/new")
def owner_vehicles_new_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("owner/vehicles.html", current_user, "chuxe", "admin")


@app.get("/owner/vehicles/{vehicle_id}")
def owner_vehicle_detail_page(vehicle_id: str, current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("owner/vehicles.html", current_user, "chuxe", "admin")


@app.get("/owner/availability")
def owner_availability_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("owner/availability.html", current_user, "chuxe", "admin")


@app.get("/owner/contracts")
def owner_contracts_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("owner/contracts.html", current_user, "chuxe", "admin")


@app.get("/owner/contracts/{contract_id}")
def owner_contract_detail_page(contract_id: str, current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("owner/contracts.html", current_user, "chuxe", "admin")


@app.get("/owner/damages")
def owner_damages_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("owner/disputes.html", current_user, "chuxe", "admin")


@app.get("/owner/disputes")
def owner_disputes_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("owner/disputes.html", current_user, "chuxe", "admin")


@app.get("/renter/dashboard")
def renter_dashboard_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("renter/dashboard.html", current_user, "khach", "admin")


@app.get("/renter/vehicles")
def renter_vehicles_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("renter/vehicles.html", current_user, "khach", "admin")


@app.get("/renter/vehicles/{vehicle_id}")
def renter_vehicle_detail_page(vehicle_id: str, current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("renter/vehicles.html", current_user, "khach", "admin")


@app.get("/renter/bookings")
def renter_bookings_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("renter/bookings.html", current_user, "khach", "admin")


@app.get("/renter/bookings/{booking_id}")
def renter_booking_detail_page(booking_id: str, current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("renter/bookings.html", current_user, "khach", "admin")


@app.get("/renter/contracts")
def renter_contracts_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("renter/contracts.html", current_user, "khach", "admin")


@app.get("/renter/contracts/{contract_id}")
def renter_contract_detail_page(contract_id: str, current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("renter/contracts.html", current_user, "khach", "admin")


@app.get("/renter/deposits")
def renter_deposits_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("renter/deposits.html", current_user, "khach", "admin")


@app.get("/renter/returns")
def renter_returns_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("renter/contracts.html", current_user, "khach", "admin")


@app.get("/admin/dashboard")
def admin_dashboard_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("admin/dashboard.html", current_user, "admin")


@app.get("/admin/users")
def admin_users_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("admin/users.html", current_user, "admin")


@app.get("/admin/vehicles")
def admin_vehicles_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("admin/vehicles.html", current_user, "admin")


@app.get("/admin/bookings")
def admin_bookings_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("admin/bookings.html", current_user, "admin")


@app.get("/admin/contracts")
def admin_contracts_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("admin/contracts.html", current_user, "admin")


@app.get("/admin/disputes")
def admin_disputes_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("admin/disputes.html", current_user, "admin")


@app.get("/admin/chain")
def admin_chain_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("admin/chain.html", current_user, "admin")


@app.get("/admin/debug")
def admin_debug_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("admin/debug.html", current_user, "admin")


@app.get("/finance")
def finance_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("finance/index.html", current_user, "admin")


@app.get("/finance/contracts/{contract_id}")
def finance_contract_page(contract_id: str, current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("finance/index.html", current_user, "admin")


@app.get("/chain")
def chain_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("finance/chain.html", current_user, "admin")


@app.get("/blockchain")
def blockchain_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("finance/chain.html", current_user, "admin")


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


@app.post("/auth/wallet/challenge")
def auth_wallet_challenge(req: WalletNonceRequest, current_user: Optional[dict] = Depends(optional_current_user)):
    try:
        return require_auth_service().create_wallet_nonce(_optional_user_payload(current_user), req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/auth/wallet/nonce")
def auth_wallet_nonce(req: WalletNonceRequest, current_user: Optional[dict] = Depends(optional_current_user)):
    try:
        return require_auth_service().create_wallet_nonce(_optional_user_payload(current_user), req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/auth/wallet/verify")
def auth_wallet_verify(req: WalletVerifyRequest, current_user: Optional[dict] = Depends(optional_current_user)):
    try:
        return require_auth_service().verify_wallet(_optional_user_payload(current_user), req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/wallet/link/challenge")
def wallet_link_challenge(req: WalletNonceRequest, current_user: dict = Depends(require_active_user)):
    try:
        req.purpose = "link_wallet"
        return require_auth_service().create_wallet_nonce(current_user["user"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/wallet/link/verify")
def wallet_link_verify(req: WalletVerifyRequest, current_user: dict = Depends(require_active_user)):
    try:
        req.purpose = "link_wallet"
        return require_auth_service().verify_wallet(current_user["user"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/auth/wallet/step-up/challenge")
def wallet_step_up_challenge(req: WalletNonceRequest, current_user: dict = Depends(require_active_user)):
    try:
        req.purpose = "step_up"
        return require_auth_service().create_wallet_nonce(current_user["user"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/auth/wallet/step-up/verify")
def wallet_step_up_verify(req: WalletVerifyRequest, current_user: dict = Depends(require_active_user)):
    try:
        req.purpose = "step_up"
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


@app.get("/api/dashboard")
def api_dashboard(current_user: dict = Depends(require_active_user)):
    try:
        overview = _filter_overview_for_user(require_service().overview(), current_user)
        role = _user_role(current_user)
        return {
            "role": role,
            "user": current_user["user"],
            "stats": {
                "vehicles": len(overview.get("vehicles") or []),
                "bookings": len(overview.get("bookings") or []),
                "contracts": len(overview.get("contracts") or []),
                "deposits": len(overview.get("deposits") or []),
                "disputes": len(overview.get("disputes") or []),
            },
        }
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


@app.get("/api/vehicles/public")
def api_public_vehicles():
    try:
        return {"items": require_service().list_public_vehicles()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/vehicles")
def api_add_vehicle(req: AddVehicleRequest, current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        return require_service().add_vehicle(current_user["user"]["id"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/owner/vehicles")
def api_owner_vehicles(current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        return {"items": require_service().list_owner_vehicles(current_user["user"]["id"])}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/api/admin/vehicles/{vehicle_id}/status")
def api_admin_update_vehicle_status(vehicle_id: str, req: UpdateVehicleStatusRequest, current_user: dict = Depends(_require_admin)):
    try:
        return require_service().update_vehicle_status(vehicle_id, req.trangthai)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/owner/availability")
def api_add_owner_availability(req: CreateAvailabilityRequest, current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        return require_service().add_availability(
            owner_id=current_user["user"]["id"],
            xe_id=req.xeid,
            ngay_bat_dau=req.ngaybatdau,
            ngay_ket_thuc=req.ngayketthuc,
            con_trong=req.controng,
            ghi_chu=req.ghichu,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/owner/availability")
def api_owner_availability(current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        return {"items": require_service().list_owner_availability(current_user["user"]["id"])}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/bookings")
def api_create_booking(req: CreateBookingRequest, current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "khach", "admin")
        return require_service().create_booking(current_user["user"]["id"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/renter/bookings")
def api_renter_bookings(current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "khach", "admin")
        return {"items": require_service().list_renter_bookings(current_user["user"]["id"])}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/owner/bookings")
def api_owner_bookings(current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        return {"items": require_service().list_owner_bookings(current_user["user"]["id"])}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/bookings/{booking_id}/approve")
def api_approve_booking(booking_id: str, req: ApproveBookingRequest, current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        return require_service().approve_booking(booking_id, current_user["user"]["id"], req.tongtiencoc)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/bookings/{booking_id}/reject")
def api_reject_booking(booking_id: str, req: RejectBookingRequest, current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        return require_service().reject_booking(booking_id, current_user["user"]["id"], req.lydo)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/from-booking")
def api_create_contract_from_booking(req: CreateContractRequest, current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        return require_service().create_contract_from_booking(req, current_user["user"]["id"], _user_role(current_user))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/create")
def api_create_contract(req: CreateContractRequest, current_user: dict = Depends(require_active_user)):
    return api_create_contract_from_booking(req, current_user)


@app.get("/api/renter/contracts")
def api_renter_contracts(current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "khach", "admin")
        return {"items": require_service().list_contracts_for_user(current_user["user"]["id"])}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/owner/contracts")
def api_owner_contracts(current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        return {"items": require_service().list_contracts_for_user(current_user["user"]["id"])}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/lock-deposit")
def api_lock_deposit(contract_id: str, current_user: dict = Depends(_require_recent_step_up)):
    try:
        contract = require_service().one("contracts", id=contract_id)
        _require_same_user_or_admin(current_user, contract.get("nguoithueid"), "Chi nguoi thue hoac admin moi duoc khoa coc")
        return require_service().lock_deposit(contract_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/owner-confirm-handover")
def api_owner_confirm_handover(contract_id: str, req: ConfirmContractStepRequest, current_user: dict = Depends(_require_recent_step_up)):
    try:
        contract = require_service().one("contracts", id=contract_id)
        _require_same_user_or_admin(current_user, contract.get("chuxeid"), "Chi chu xe hoac admin moi duoc xac nhan giao xe")
        return require_service().owner_confirm_handover(contract_id, current_user["user"]["id"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/renter-confirm-receive")
def api_renter_confirm_receive(contract_id: str, req: ConfirmContractStepRequest, current_user: dict = Depends(_require_recent_step_up)):
    try:
        contract = require_service().one("contracts", id=contract_id)
        _require_same_user_or_admin(current_user, contract.get("nguoithueid"), "Chi nguoi thue hoac admin moi duoc xac nhan nhan xe")
        return require_service().renter_confirm_receive(contract_id, current_user["user"]["id"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/return-vehicle")
def api_return_vehicle(contract_id: str, req: ReturnVehicleRequest, current_user: dict = Depends(_require_recent_step_up)):
    try:
        contract = require_service().one("contracts", id=contract_id)
        _require_same_user_or_admin(current_user, contract.get("nguoithueid"), "Chi nguoi thue hoac admin moi duoc tra xe")
        return require_service().return_vehicle(contract_id, current_user["user"]["id"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/owner-confirm-return")
def api_owner_confirm_return(contract_id: str, req: ConfirmContractStepRequest, current_user: dict = Depends(_require_recent_step_up)):
    try:
        contract = require_service().one("contracts", id=contract_id)
        _require_same_user_or_admin(current_user, contract.get("chuxeid"), "Chi chu xe hoac admin moi duoc xac nhan nhan lai xe")
        return require_service().owner_confirm_return(contract_id, current_user["user"]["id"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/damage-claim")
def api_damage_claim(contract_id: str, req: CreateDamageClaimRequest, current_user: dict = Depends(_require_recent_step_up)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        contract = require_service().one("contracts", id=contract_id)
        _require_same_user_or_admin(current_user, contract.get("chuxeid"), "Chi chu xe hoac admin moi duoc tao damage claim")
        return require_service().create_damage_claim(contract_id, current_user["user"]["id"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/owner/disputes")
def api_owner_disputes(current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "chuxe", "admin")
        return {"items": require_service().list_disputes_for_owner(current_user["user"]["id"])}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/renter/deposits")
def api_renter_deposits(current_user: dict = Depends(require_active_user)):
    try:
        _require_roles(current_user, "khach", "admin")
        return {"items": require_service().list_deposits_for_renter(current_user["user"]["id"])}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/disputes/{dispute_id}/admin-confirm-no-damage")
def api_admin_confirm_no_damage(dispute_id: str, req: AdminConfirmNoDamageRequest, current_user: dict = Depends(_require_recent_step_up)):
    try:
        _require_roles(current_user, "admin")
        return require_service().admin_confirm_no_damage(dispute_id, current_user["user"]["id"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/disputes/{dispute_id}/admin-confirm-damage")
def api_admin_confirm_damage(dispute_id: str, req: AdminConfirmDamageRequest, current_user: dict = Depends(_require_recent_step_up)):
    try:
        _require_roles(current_user, "admin")
        return require_service().admin_confirm_damage(dispute_id, current_user["user"]["id"], req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/settle")
def api_settle_contract(contract_id: str, req: SettleContractRequest, current_user: dict = Depends(_require_recent_step_up)):
    try:
        contract = require_service().one("contracts", id=contract_id)
        renter_id = contract.get("nguoithueid")
        if not _is_admin(current_user) and current_user["user"].get("id") != renter_id:
            raise HTTPException(status_code=403, detail="Chi renter lien quan hoac admin moi duoc tat toan contract")
        return require_service().settle_contract(
            contract_id=contract_id,
            tong_tien_thanh_toan=req.tongtienthanhtoan,
            tong_tien_hoan_lai=req.tongtienhoanlai,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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


@app.post("/api/internal/jobs/resolve-expired-bookings")
def api_resolve_expired_bookings_job(
    req: Optional[ResolveExpiredBookingsRequest] = None,
    limit: Optional[int] = None,
    job_secret: Optional[str] = Header(default=None, alias="X-Internal-Job-Secret"),
):
    try:
        if not BOOKING_JOB_SECRET:
            raise HTTPException(status_code=503, detail="BOOKING_JOB_SECRET chua duoc cau hinh")
        if job_secret != BOOKING_JOB_SECRET:
            raise HTTPException(status_code=403, detail="Sai X-Internal-Job-Secret")
        effective_limit = limit if limit is not None else (100 if req is None else req.limit)
        return require_service().resolve_expired_pending_bookings(effective_limit or 100)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/admin/users")
def api_admin_users(current_user: dict = Depends(_require_admin)):
    try:
        rows = require_service().t("users").select("*").order("taoluc", desc=True).limit(500).execute().data or []
        return {"items": rows}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/admin/vehicles")
def api_admin_vehicles(current_user: dict = Depends(_require_admin)):
    try:
        rows = require_service().list_admin_vehicles()
        return {"items": rows}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/admin/bookings")
def api_admin_bookings(current_user: dict = Depends(_require_admin)):
    try:
        rows = require_service().t("bookings").select("*").order("taoluc", desc=True).limit(500).execute().data or []
        return {"items": rows}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/admin/contracts")
def api_admin_contracts(current_user: dict = Depends(_require_admin)):
    try:
        rows = require_service().t("contracts").select("*").order("taoluc", desc=True).limit(500).execute().data or []
        return {"items": rows}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/admin/disputes")
def api_admin_disputes(current_user: dict = Depends(_require_admin)):
    try:
        rows = require_service().t("disputes").select("*").order("taoluc", desc=True).limit(500).execute().data or []
        return {"items": rows}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/owner/bookings")
def owner_bookings_page(current_user: Optional[dict] = Depends(optional_current_user)):
    return _role_page("owner/bookings.html", current_user, "chuxe", "admin")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)

