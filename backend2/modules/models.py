from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .utils import normalize_non_empty_str


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AddVehicleRequest(StrictBaseModel):
    owneremail: str = Field(alias="ownerEmail")
    bienso: str = Field(alias="bienSo")
    hangxe: str = Field(alias="hangXe")
    dongxe: str = Field(alias="dongXe")
    loaixe: str = Field(default="Sedan", alias="loaiXe")
    giatheongay: float = Field(default=0, alias="giaTheoNgay")
    giatheogio: float = Field(default=0, alias="giaTheoGio")
    namsanxuat: Optional[int] = Field(default=None, alias="namSanXuat")
    mota: Optional[str] = Field(default=None, alias="moTa")


class CreateBookingRequest(StrictBaseModel):
    renteremail: str = Field(alias="renterEmail")
    bienso: str = Field(alias="bienSo")
    songaythue: int = Field(default=1, alias="soNgayThue")
    diadiemnhan: str = Field(alias="diaDiemNhan")
    tongtienthue: float = Field(alias="tongTienThue")
    ghichu: Optional[str] = Field(default=None, alias="ghiChu")


class CreateContractRequest(StrictBaseModel):
    dangkyid: str = Field(alias="dangKyId")
    tongtiencoc: float = Field(alias="tongTienCoc")


class SettleContractRequest(StrictBaseModel):
    tongtienthanhtoan: float = Field(alias="tongTienThanhToan")
    tongtienhoanlai: float = Field(default=0, alias="tongTienHoanLai")


class ReturnVehicleRequest(StrictBaseModel):
    nguoitraid: str = Field(alias="nguoiTraId")
    ghichu: str = Field(alias="ghiChu")
    evidenceurls: list[str] = Field(default_factory=list, alias="evidenceUrls")
    evidencemeta: dict[str, Any] = Field(default_factory=dict, alias="evidenceMeta")

    @field_validator("nguoitraid", "ghichu")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)


class CreateDamageClaimRequest(StrictBaseModel):
    ownerid: str = Field(alias="ownerId")
    lydo: str = Field(alias="lyDo")
    estimatedcost: float = Field(default=0, alias="estimatedCost")
    evidenceurls: list[str] = Field(default_factory=list, alias="evidenceUrls")
    evidencemeta: dict[str, Any] = Field(default_factory=dict, alias="evidenceMeta")
    ghichu: Optional[str] = Field(default=None, alias="ghiChu")

    @field_validator("ownerid", "lydo")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)

    @field_validator("estimatedcost")
    @classmethod
    def validate_estimated_cost(cls, value: float):
        if value < 0:
            raise ValueError("estimatedCost phai >= 0")
        return value


class AdminConfirmNoDamageRequest(StrictBaseModel):
    adminid: str = Field(alias="adminId")
    decisionnote: str = Field(alias="decisionNote")
    evidencemeta: dict[str, Any] = Field(default_factory=dict, alias="evidenceMeta")

    @field_validator("adminid", "decisionnote")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)


class AdminConfirmDamageRequest(StrictBaseModel):
    adminid: str = Field(alias="adminId")
    approvedcost: float = Field(alias="approvedCost")
    decisionnote: str = Field(alias="decisionNote")
    evidencemeta: dict[str, Any] = Field(default_factory=dict, alias="evidenceMeta")

    @field_validator("adminid", "decisionnote")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)

    @field_validator("approvedcost")
    @classmethod
    def validate_approved_cost(cls, value: float):
        if value < 0:
            raise ValueError("approvedCost phai >= 0")
        return value
