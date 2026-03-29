import base64
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Optional
from uuid import uuid4

try:
    import bcrypt  # type: ignore
except ModuleNotFoundError:
    bcrypt = None
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import Header, HTTPException
from supabase import Client

from .auth_models import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    MeResponse,
    WalletNonceRequest,
    WalletNonceResponse,
    WalletUnlinkRequest,
    WalletUnlinkResponse,
    WalletVerifyRequest,
    WalletVerifyResponse,
)
from .config import JWT_EXPIRE_MINUTES, JWT_SECRET, SIWE_DOMAIN, SIWE_URI, SYSTEM_ESCROW_ADDRESS, TABLES
from .utils import now_iso, sha256_text


class AuthService:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    def t(self, key: str):
        return self.supabase.table(TABLES[key])

    def maybe_one(self, table_key: str, **filters) -> Optional[dict]:
        query = self.t(table_key).select("*")
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.limit(1).execute()
        return result.data[0] if result.data else None

    def one(self, table_key: str, **filters) -> dict:
        result = self.maybe_one(table_key, **filters)
        if result is None:
            raise ValueError(f"Khong tim thay du lieu trong bang {TABLES[table_key]} voi {filters}")
        return result

    def insert(self, table_key: str, payload: dict) -> dict:
        result = self.t(table_key).insert(payload).execute()
        if not result.data:
            raise ValueError(f"Insert vao {TABLES[table_key]} khong tra ve du lieu")
        return result.data[0]

    def update(self, table_key: str, match_field: str, match_value, payload: dict) -> dict:
        result = self.t(table_key).update(payload).eq(match_field, match_value).execute()
        if not result.data:
            raise ValueError(f"Update {TABLES[table_key]} that bai")
        return result.data[0]

    def _find_user_by_identifier(self, identifier: str) -> Optional[dict]:
        for field in ("email", "sodienthoai"):
            user = self.maybe_one("users", **{field: identifier})
            if user:
                return user
        return None

    def _verify_password(self, password: str, mk_hash: str) -> bool:
        if not mk_hash:
            return False
        if mk_hash.startswith(("$2a$", "$2b$", "$2y$")):
            if bcrypt is None:
                raise ValueError("mkHash dang o dinh dang bcrypt nhung moi truong chua cai bcrypt")
            return bcrypt.checkpw(password.encode("utf-8"), mk_hash.encode("utf-8"))
        if mk_hash.startswith("sha256$"):
            return sha256_text(password) == mk_hash.split("$", 1)[1]
        if len(mk_hash) == 64 and all(char in "0123456789abcdef" for char in mk_hash.lower()):
            return sha256_text(password) == mk_hash.lower()
        return hmac.compare_digest(password, mk_hash)

    def _b64url_encode(self, value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("utf-8")

    def _b64url_decode(self, value: str) -> bytes:
        padding = '=' * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)

    def _encode_jwt(self, payload: dict) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        header_segment = self._b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_segment = self._b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
        signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, sha256).digest()
        return f"{header_segment}.{payload_segment}.{self._b64url_encode(signature)}"

    def _decode_jwt(self, token: str) -> dict:
        try:
            header_segment, payload_segment, signature_segment = token.split(".")
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Token khong hop le") from exc
        signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
        expected_signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, sha256).digest()
        actual_signature = self._b64url_decode(signature_segment)
        if not hmac.compare_digest(expected_signature, actual_signature):
            raise HTTPException(status_code=401, detail="Token signature khong hop le")
        payload = json.loads(self._b64url_decode(payload_segment).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(status_code=401, detail="Token da het han")
        return payload

    def _sanitize_user(self, user: dict) -> dict:
        return {
            "id": user.get("id"),
            "hoTen": user.get("hoten") or user.get("hoTen"),
            "email": user.get("email"),
            "soDienThoai": user.get("sodienthoai") or user.get("soDienThoai"),
            "vaiTro": user.get("vaitro") or user.get("vaiTro"),
            "trangThai": user.get("trangthai") or user.get("trangThai"),
        }

    def _active_session(self, jti: str) -> Optional[dict]:
        session = self.maybe_one("auth_sessions", jti=jti)
        if not session or session.get("revokedat"):
            return None
        expires_at = session.get("expiresat")
        if expires_at and datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < datetime.now(timezone.utc):
            return None
        return session

    def _list_wallets_for_user(self, user_id: str) -> list[dict]:
        result = self.t("wallets").select("*").eq("nguoidungid", user_id).limit(20).execute()
        return result.data or []

    def _hash_password_for_storage(self, password: str) -> str:
        if bcrypt is not None:
            return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        return f"sha256${sha256_text(password)}"

    def _log_auth_event(self, action: str, **fields):
        details = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
        print(f"[AUTH] {now_iso()} action={action} {details}".strip())

    def register(self, req: RegisterRequest) -> RegisterResponse:
        if not req.email and not req.sodienthoai:
            raise ValueError("Can cung cap it nhat email hoac soDienThoai")
        if req.email and self.maybe_one("users", email=req.email):
            raise ValueError("Email da ton tai")
        if req.sodienthoai and self.maybe_one("users", sodienthoai=req.sodienthoai):
            raise ValueError("So dien thoai da ton tai")
        self._log_auth_event("register_attempt", email=req.email, soDienThoai=req.sodienthoai)
        user = self.insert("users", {
            "hoten": req.hoten,
            "email": req.email,
            "sodienthoai": req.sodienthoai,
            "mkhash": self._hash_password_for_storage(req.password),
            "vaitro": "khach",
            "trangthai": "hoatDong",
            "diemdanhgiatb": 0,
            "taoluc": now_iso(),
            "capnhatluc": now_iso(),
        })
        self._log_auth_event("register_success", userId=user.get("id"), email=user.get("email"), soDienThoai=user.get("sodienthoai"))
        return RegisterResponse(user=self._sanitize_user(user), note="Dang ky thanh cong")

    def login(self, req: LoginRequest) -> LoginResponse:
        self._log_auth_event("login_attempt", identifier=req.identifier)
        user = self._find_user_by_identifier(req.identifier)
        if user is None or not self._verify_password(req.password, user.get("mkhash", "")):
            self._log_auth_event("login_failed", identifier=req.identifier, reason="invalid_credentials")
            raise ValueError("Thong tin dang nhap khong hop le")
        if (user.get("trangthai") or user.get("trangThai")) != "hoatDong":
            self._log_auth_event("login_failed", identifier=req.identifier, userId=user.get("id"), reason="inactive_user")
            raise ValueError("Tai khoan khong o trang thai cho phep dang nhap")

        self.update("users", "id", user["id"], {"landangnhapcuoi": now_iso(), "capnhatluc": now_iso()})
        now_ts = datetime.now(timezone.utc)
        expires_at = now_ts + timedelta(minutes=JWT_EXPIRE_MINUTES)
        jti = f"SES{uuid4().hex}"
        payload = {
            "sub": user["id"],
            "role": user.get("vaitro") or user.get("vaiTro"),
            "jti": jti,
            "exp": int(expires_at.timestamp()),
        }
        token = self._encode_jwt(payload)
        self.insert("auth_sessions", {
            "jti": jti,
            "nguoidungid": user["id"],
            "tokenhash": sha256_text(token),
            "createdat": now_iso(),
            "expiresat": expires_at.isoformat(),
            "revokedat": None,
            "lastseenat": now_iso(),
        })
        self._log_auth_event("login_success", userId=user.get("id"), identifier=req.identifier, jti=jti)
        return LoginResponse(accessToken=token, expiresIn=JWT_EXPIRE_MINUTES * 60, user=self._sanitize_user(user))

    def get_current_user(self, token: str) -> dict:
        payload = self._decode_jwt(token)
        session = self._active_session(payload["jti"])
        if session is None:
            raise HTTPException(status_code=401, detail="Session khong hop le hoac da logout")
        user = self.one("users", id=payload["sub"])
        if (user.get("trangthai") or user.get("trangThai")) != "hoatDong":
            raise HTTPException(status_code=403, detail="Tai khoan khong con hoat dong")
        self.update("auth_sessions", "jti", payload["jti"], {"lastseenat": now_iso()})
        return {"user": user, "session": session, "payload": payload}

    def me(self, token: str) -> MeResponse:
        auth_context = self.get_current_user(token)
        return MeResponse(user=self._sanitize_user(auth_context["user"]), wallets=self._list_wallets_for_user(auth_context["user"]["id"]), session={"jti": auth_context["session"].get("jti"), "expiresAt": auth_context["session"].get("expiresat")})

    def logout(self, token: str) -> dict:
        payload = self._decode_jwt(token)
        session = self._active_session(payload["jti"])
        if session is None:
            self._log_auth_event("logout_skip", reason="session_missing_or_revoked")
            return {"loggedOut": True, "note": "Token da het hieu luc hoac da logout truoc do"}
        self.update("auth_sessions", "jti", payload["jti"], {"revokedat": now_iso()})
        self._log_auth_event("logout_success", userId=session.get("nguoidungid"), jti=payload.get("jti"))
        return {"loggedOut": True}

    def _build_siwe_message(self, wallet_address: str, chain_id: int, nonce: str, purpose: str) -> str:
        issued_at = now_iso()
        statement = "Lien ket vi voi tai khoan CarRentalAutoPayment" if purpose == "link_wallet" else "Dang nhap vao CarRentalAutoPayment"
        return (
            f"{SIWE_DOMAIN} wants you to sign in with your Ethereum account:\n"
            f"{wallet_address}\n\n"
            f"{statement}\n\n"
            f"URI: {SIWE_URI}\n"
            f"Version: 1\n"
            f"Chain ID: {chain_id}\n"
            f"Nonce: {nonce}\n"
            f"Issued At: {issued_at}\n"
            f"Request ID: {purpose}"
        )

    def create_wallet_nonce(self, current_user: dict, req: WalletNonceRequest) -> WalletNonceResponse:
        nonce = secrets.token_hex(8)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        message = self._build_siwe_message(req.walletaddress, req.chainid, nonce, req.purpose)
        self._log_auth_event("wallet_nonce_created", userId=current_user.get("id"), walletAddress=req.walletaddress.lower(), purpose=req.purpose, chainId=req.chainid)
        challenge = self.insert("wallet_auth_challenges", {
            "nguoidungid": current_user["id"],
            "walletaddress": req.walletaddress.lower(),
            "nonce": nonce,
            "purpose": req.purpose,
            "siwemessage": message,
            "chainid": req.chainid,
            "expiresat": expires_at.isoformat(),
            "usedat": None,
            "createdat": now_iso(),
        })
        return WalletNonceResponse(walletAddress=challenge["walletaddress"], nonce=challenge["nonce"], message=challenge["siwemessage"], expiresAt=challenge["expiresat"], purpose=challenge["purpose"])

    def _get_active_challenge(self, user_id: str, wallet_address: str, purpose: str) -> dict:
        result = self.t("wallet_auth_challenges").select("*").eq("nguoidungid", user_id).eq("walletaddress", wallet_address.lower()).eq("purpose", purpose).order("createdat", desc=True).limit(10).execute()
        for challenge in result.data or []:
            if challenge.get("usedat"):
                continue
            expires_at = datetime.fromisoformat(challenge["expiresat"].replace("Z", "+00:00"))
            if expires_at < datetime.now(timezone.utc):
                continue
            return challenge
        raise ValueError("Khong tim thay challenge hop le")

    def verify_wallet(self, current_user: dict, req: WalletVerifyRequest) -> WalletVerifyResponse:
        challenge = self._get_active_challenge(current_user["id"], req.walletaddress, req.purpose)
        if challenge.get("siwemessage") != req.message:
            raise ValueError("Message khong khop challenge da tao")
        recovered_address = Account.recover_message(encode_defunct(text=req.message), signature=req.signature)
        if recovered_address.lower() != req.walletaddress.lower():
            raise ValueError("Chu ky khong khop voi walletAddress")

        existing_wallet = self.maybe_one("wallets", address=req.walletaddress.lower()) or self.maybe_one("wallets", address=req.walletaddress)
        if existing_wallet and existing_wallet.get("nguoidungid") not in {None, current_user["id"]}:
            raise ValueError("Vi nay da lien ket voi tai khoan khac")

        if existing_wallet:
            wallet = self.update("wallets", "id", existing_wallet["id"], {
                "nguoidungid": current_user["id"],
                "status": "active",
                "wallettype": existing_wallet.get("wallettype") or "user",
                "syncat": now_iso(),
            })
        else:
            wallet = self.insert("wallets", {
                "nguoidungid": current_user["id"],
                "address": req.walletaddress.lower(),
                "wallettype": "user",
                "status": "active",
                "balance": 0,
                "lockedbalance": 0,
                "syncat": now_iso(),
                "createdat": now_iso(),
            })

        challenge = self.update("wallet_auth_challenges", "id", challenge["id"], {"usedat": now_iso()})
        self._log_auth_event("wallet_verify_success", userId=current_user.get("id"), walletAddress=wallet.get("address"), purpose=req.purpose)
        return WalletVerifyResponse(verified=True, wallet=wallet, challenge=challenge)

    def unlink_wallet(self, current_user: dict, req: WalletUnlinkRequest) -> WalletUnlinkResponse:
        wallet = self.maybe_one("wallets", address=req.walletaddress.lower()) or self.maybe_one("wallets", address=req.walletaddress)
        if wallet is None or wallet.get("nguoidungid") != current_user["id"]:
            raise ValueError("Khong tim thay vi thuoc tai khoan hien tai")
        if (wallet.get("wallettype") or "").lower() == "system" or wallet.get("address") == SYSTEM_ESCROW_ADDRESS:
            raise ValueError("Khong duoc go vi he thong")
        wallet = self.update("wallets", "id", wallet["id"], {
            "nguoidungid": None,
            "status": "inactive",
            "syncat": now_iso(),
        })
        self._log_auth_event("wallet_unlink_success", userId=current_user.get("id"), walletAddress=wallet.get("address"))
        return WalletUnlinkResponse(unlinked=True, wallet=wallet)


def extract_bearer_token(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Thieu Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Authorization header khong hop le")
    return token
