from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .utils import normalize_non_empty_str


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AddVehicleRequest(StrictBaseModel):
    bienso: str = Field(alias="bienSo")
    hangxe: str = Field(alias="hangXe")
    dongxe: str = Field(alias="dongXe")
    loaixe: str = Field(alias="loaiXe")
    giatheongay: float = Field(default=0, alias="giaTheoNgay")
    giatheogio: float = Field(default=0, alias="giaTheoGio")
    namsanxuat: Optional[int] = Field(default=None, alias="namSanXuat")
    mota: Optional[str] = Field(default=None, alias="moTa")
    baohiem: Optional[str] = Field(default=None, alias="baoHiem")
    dangkiem: Optional[str] = Field(default=None, alias="dangKiem")
    dangkyxe: Optional[str] = Field(default=None, alias="dangKyXe")
    ngayhethandangkiem: Optional[str] = Field(default=None, alias="ngayHetHanDangKiem")

    @field_validator("bienso", "hangxe", "dongxe", "loaixe")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)

    @field_validator("giatheongay", "giatheogio")
    @classmethod
    def validate_non_negative_price(cls, value: float):
        if value < 0:
            raise ValueError("Gia khong duoc am")
        return value


class CreateAvailabilityRequest(StrictBaseModel):
    xeid: str = Field(alias="xeId")
    ngaybatdau: str = Field(alias="ngayBatDau")
    ngayketthuc: str = Field(alias="ngayKetThuc")
    controng: bool = Field(default=True, alias="conTrong")
    ghichu: Optional[str] = Field(default=None, alias="ghiChu")

    @field_validator("xeid", "ngaybatdau", "ngayketthuc")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)

    @model_validator(mode="after")
    def validate_range(self):
        try:
            start = datetime.fromisoformat(str(self.ngaybatdau).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(self.ngayketthuc).replace("Z", "+00:00"))
        except Exception as exc:
            raise ValueError("ngayBatDau/ngayKetThuc khong dung dinh dang ISO") from exc
        if end <= start:
            raise ValueError("ngayKetThuc phai lon hon ngayBatDau")
        return self


class CreateBookingRequest(StrictBaseModel):
    xeid: str = Field(alias="xeId")
    songaythue: Optional[int] = Field(default=None, alias="soNgayThue")
    ngaybatdau: Optional[str] = Field(default=None, alias="ngayBatDau")
    ngayketthuc: Optional[str] = Field(default=None, alias="ngayKetThuc")
    diadiemnhan: str = Field(alias="diaDiemNhan")
    tongtienthue: Optional[float] = Field(default=None, alias="tongTienThue")
    ghichu: Optional[str] = Field(default=None, alias="ghiChu")

    @field_validator("xeid", "diadiemnhan")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)

    @field_validator("songaythue")
    @classmethod
    def validate_days(cls, value: Optional[int]):
        if value is not None and value < 1:
            raise ValueError("soNgayThue phai >= 1")
        return value

    @field_validator("tongtienthue")
    @classmethod
    def validate_price(cls, value: Optional[float]):
        if value is not None and value < 0:
            raise ValueError("tongTienThue phai >= 0")
        return value


class CreateContractRequest(StrictBaseModel):
    dangkyid: str = Field(alias="dangKyId")
    tongtiencoc: float = Field(alias="tongTienCoc")

    @field_validator("dangkyid")
    @classmethod
    def validate_booking_id(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)

    @field_validator("tongtiencoc")
    @classmethod
    def validate_deposit(cls, value: float):
        if value < 0:
            raise ValueError("tongTienCoc phai >= 0")
        return value


class SettleContractRequest(StrictBaseModel):
    tongtienthanhtoan: float = Field(alias="tongTienThanhToan")
    tongtienhoanlai: float = Field(default=0, alias="tongTienHoanLai")


class UpdateVehicleStatusRequest(StrictBaseModel):
    trangthai: str = Field(alias="trangThai")

    @field_validator("trangthai")
    @classmethod
    def validate_status(cls, value: str, info):
        status = normalize_non_empty_str(value, info.field_name)
        allowed = {"choDuyet", "sanSang", "dangThue", "baoTri", "ngungHoatDong"}
        if status not in allowed:
            raise ValueError("trangThai khong hop le")
        return status


class ReturnVehicleRequest(StrictBaseModel):
    ghichu: str = Field(alias="ghiChu")
    evidenceurls: list[str] = Field(default_factory=list, alias="evidenceUrls")
    evidencemeta: dict[str, Any] = Field(default_factory=dict, alias="evidenceMeta")

    @field_validator("ghichu")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)


class ConfirmContractStepRequest(StrictBaseModel):
    ghichu: str = Field(alias="ghiChu")
    evidenceurls: list[str] = Field(default_factory=list, alias="evidenceUrls")
    evidencemeta: dict[str, Any] = Field(default_factory=dict, alias="evidenceMeta")

    @field_validator("ghichu")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)


class CreateDamageClaimRequest(StrictBaseModel):
    lydo: str = Field(alias="lyDo")
    estimatedcost: float = Field(default=0, alias="estimatedCost")
    evidenceurls: list[str] = Field(default_factory=list, alias="evidenceUrls")
    evidencemeta: dict[str, Any] = Field(default_factory=dict, alias="evidenceMeta")
    ghichu: Optional[str] = Field(default=None, alias="ghiChu")

    @field_validator("lydo")
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
    decisionnote: str = Field(alias="decisionNote")
    evidencemeta: dict[str, Any] = Field(default_factory=dict, alias="evidenceMeta")

    @field_validator("decisionnote")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)


class AdminConfirmDamageRequest(StrictBaseModel):
    approvedcost: float = Field(alias="approvedCost")
    decisionnote: str = Field(alias="decisionNote")
    evidencemeta: dict[str, Any] = Field(default_factory=dict, alias="evidenceMeta")

    @field_validator("decisionnote")
    @classmethod
    def validate_required_text(cls, value: str, info):
        return normalize_non_empty_str(value, info.field_name)

    @field_validator("approvedcost")
    @classmethod
    def validate_approved_cost(cls, value: float):
        if value < 0:
            raise ValueError("approvedCost phai >= 0")
        return value

