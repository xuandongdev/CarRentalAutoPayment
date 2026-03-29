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
def api_overview():
    try:
        return require_service().overview()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/node/chain")
def api_chain():
    return node_storage.export_chain()


@app.post("/api/node/reconcile")
def api_reconcile_chain():
    try:
        return require_service().reconcile_chain_to_db()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/node/reconcile")
def api_reconcile_chain_get():
    return api_reconcile_chain()


@app.post("/api/vehicles")
def api_add_vehicle(req: AddVehicleRequest):
    try:
        return require_service().add_vehicle(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/bookings")
def api_create_booking(req: CreateBookingRequest):
    try:
        return require_service().create_booking(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/from-booking")
def api_create_contract_from_booking(req: CreateContractRequest):
    try:
        return require_service().create_contract_from_booking(req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/create")
def api_create_contract(req: CreateContractRequest):
    return api_create_contract_from_booking(req)


@app.post("/api/contracts/{contract_id}/lock-deposit")
def api_lock_deposit(contract_id: str):
    try:
        return require_service().lock_deposit(contract_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/return-vehicle")
def api_return_vehicle(contract_id: str, req: ReturnVehicleRequest):
    try:
        return require_service().return_vehicle(contract_id, req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/damage-claim")
def api_damage_claim(contract_id: str, req: CreateDamageClaimRequest):
    try:
        return require_service().create_damage_claim(contract_id, req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/disputes/{dispute_id}/admin-confirm-no-damage")
def api_admin_confirm_no_damage(dispute_id: str, req: AdminConfirmNoDamageRequest):
    try:
        return require_service().admin_confirm_no_damage(dispute_id, req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/disputes/{dispute_id}/admin-confirm-damage")
def api_admin_confirm_damage(dispute_id: str, req: AdminConfirmDamageRequest):
    try:
        return require_service().admin_confirm_damage(dispute_id, req)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/contracts/{contract_id}/settle")
def api_settle_contract(contract_id: str, req: SettleContractRequest):
    try:
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
