from typing import Any, Optional

from pydantic import Field, field_validator

from .models import StrictBaseModel
from .utils import normalize_non_empty_str


class RegisterRequest(StrictBaseModel):
    hoten: str = Field(alias="hoTen")
    email: Optional[str] = Field(default=None, alias="email")
    sodienthoai: Optional[str] = Field(default=None, alias="soDienThoai")
    password: str = Field(alias="password")

    @field_validator("hoten", "password")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)

    @field_validator("email", "sodienthoai")
    @classmethod
    def validate_optional_text(cls, value: Optional[str]):
        if value is None:
            return value
        text = value.strip()
        return text or None


class RegisterResponse(StrictBaseModel):
    user: dict[str, Any] = Field(alias="user")
    note: str = Field(alias="note")


class LoginRequest(StrictBaseModel):
    identifier: str = Field(alias="identifier")
    password: str = Field(alias="password")

    @field_validator("identifier", "password")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)


class LoginResponse(StrictBaseModel):
    accesstoken: str = Field(alias="accessToken")
    tokentype: str = Field(default="bearer", alias="tokenType")
    expiresin: int = Field(alias="expiresIn")
    user: dict[str, Any] = Field(alias="user")


class MeResponse(StrictBaseModel):
    user: dict[str, Any] = Field(alias="user")
    wallets: list[dict[str, Any]] = Field(default_factory=list, alias="wallets")
    session: Optional[dict[str, Any]] = Field(default=None, alias="session")


class WalletNonceRequest(StrictBaseModel):
    walletaddress: str = Field(alias="walletAddress")
    chainid: int = Field(alias="chainId")
    purpose: str = Field(default="link_wallet", alias="purpose")

    @field_validator("walletaddress")
    @classmethod
    def validate_wallet(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)


class WalletNonceResponse(StrictBaseModel):
    walletaddress: str = Field(alias="walletAddress")
    nonce: str = Field(alias="nonce")
    message: str = Field(alias="message")
    expiresat: str = Field(alias="expiresAt")
    purpose: str = Field(alias="purpose")


class WalletVerifyRequest(StrictBaseModel):
    walletaddress: str = Field(alias="walletAddress")
    message: str = Field(alias="message")
    signature: str = Field(alias="signature")
    purpose: str = Field(default="link_wallet", alias="purpose")

    @field_validator("walletaddress", "message", "signature")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)


class WalletVerifyResponse(StrictBaseModel):
    verified: bool = Field(alias="verified")
    wallet: dict[str, Any] = Field(alias="wallet")
    challenge: dict[str, Any] = Field(alias="challenge")


class WalletUnlinkRequest(StrictBaseModel):
    walletaddress: str = Field(alias="walletAddress")

    @field_validator("walletaddress")
    @classmethod
    def validate_wallet(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)


class WalletUnlinkResponse(StrictBaseModel):
    unlinked: bool = Field(alias="unlinked")
    wallet: dict[str, Any] = Field(alias="wallet")
