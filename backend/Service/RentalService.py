import os
from pathlib import Path
from uuid import uuid4

try:
    from ..db import supabase
    from ..NodeStorage import LocalNodeStorage, now_iso
except (ImportError, ValueError):
    from db import supabase
    from NodeStorage import LocalNodeStorage, now_iso

BACKEND_DIR = Path(__file__).resolve().parent.parent
NODE_DATA_DIR = Path(os.getenv("NODE_DATA_DIR", "./NodeData"))
if not NODE_DATA_DIR.is_absolute():
    NODE_DATA_DIR = BACKEND_DIR / NODE_DATA_DIR

SYSTEM_ESCROW_ADDRESS = os.getenv("SYSTEM_ESCROW_ADDRESS", "0xSYSTEMESCROW")

node = LocalNodeStorage(str(NODE_DATA_DIR))

class RentalService:
    def __init__(self):
        self.db = supabase
        self.node = node

    def _one(self, table_name: str, **filters):
        query = self.db.table(table_name).select("*")
        for key, value in filters.items():
            query = query.eq(key, value)

        result = query.limit(1).execute()
        if not result.data:
            raise ValueError(f"Khong tim thay ban ghi trong bang {table_name} voi dieu kien {filters}")
        return result.data[0]

    def _insert(self, table_name: str, payload: dict):
        result = self.db.table(table_name).insert(payload).execute()
        return result.data[0] if result.data else payload

    def _update(self, table_name: str, match_field: str, match_value, payload: dict):
        result = self.db.table(table_name).update(payload).eq(match_field, match_value).execute()
        return result.data[0] if result.data else payload

    def _mirror_block_to_supabase(self, block: dict):
        self._insert("khoiChuoi", {
            "soKhoi": block["soKhoi"],
            "thoiGianKhoi": block["thoiGianKhoi"],
            "maBamKhoiTruoc": block["maBamKhoiTruoc"],
            "maBamKhoi": block["maBamKhoi"],
            "nonce": block["nonce"],
            "gocMerkle": block["gocMerkle"],
            "soLuongGiaoDich": block["soLuongGiaoDich"],
            "duLieuGoc": block,
        })

        for tx in block["danhSachGiaoDich"]:
            tx_row = self._insert("giaoDichChuoi", {
                "maGiaoDich": tx["maGiaoDich"],
                "loaiGiaoDich": tx["loaiGiaoDich"],
                "maBamDuLieu": tx["maBamDuLieu"],
                "viGui": tx["viGui"],
                "viNhan": tx["viNhan"],
                "soTien": tx["soTien"],
                "thoiGianGiaoDich": tx["thoiGianGiaoDich"],
                "chuKy": tx["chuKy"],
                "trangThai": tx["trangThai"],
                "soKhoi": tx["soKhoi"],
                "maBamKhoi": tx["maBamKhoi"],
                "hopDongThueId": tx["duLieuGoc"].get("hopDongThueId"),
                "tienCocId": tx["duLieuGoc"].get("tienCocId"),
                "tranhChapId": tx["duLieuGoc"].get("tranhChapId"),
                "duLieuGoc": tx,
            })

            self._insert("suKienChuoi", {
                "maSuKien": f'SK{uuid4().hex[:12].upper()}',
                "maGiaoDich": tx["maGiaoDich"],
                "tenSuKien": f'{tx["loaiGiaoDich"]}DaXacNhan',
                "soKhoi": tx["soKhoi"],
                "maBamKhoi": tx["maBamKhoi"],
                "duLieu": {
                    "hopDongThueId": tx["duLieuGoc"].get("hopDongThueId"),
                    "soTien": tx["soTien"],
                },
            })

    def tao_hop_dong_tu_dang_ky(self, dang_ky_id: str, tong_tien_coc: float):
        dang_ky = self._one("dangKy", id=dang_ky_id)
        xe = self._one("xe", id=dang_ky["xeId"])

        vi_nguoi_thue = self._one("vi", nguoiDungId=dang_ky["nguoiDungId"])
        vi_chu_xe = self._one("vi", nguoiDungId=xe["chuXeId"])

        hop_dong = self._insert("hopDongThue", {
            "dangKyId": dang_ky["id"],
            "xeId": dang_ky["xeId"],
            "nguoiThueId": dang_ky["nguoiDungId"],
            "chuXeId": xe["chuXeId"],
            "viNguoiThue": vi_nguoi_thue["diaChi"],
            "viChuXe": vi_chu_xe["diaChi"],
            "trangThai": "khoiTao",
            "tongTienCoc": tong_tien_coc,
            "tongTienThanhToan": 0,
            "tongTienHoanLai": 0,
            "daGiaoXe": False,
            "daNhanLaiXe": False,
        })

        tien_coc = self._insert("tienCoc", {
            "hopDongThueId": hop_dong["id"],
            "tongHoaCoc": tong_tien_coc,
            "thoaThuanCoc": "Dat coc truoc khi nhan xe",
            "soTienKhoaCoc": 0,
            "soTienHoanCoc": 0,
            "heThongXuLy": False,
            "trangThai": "chuaKhoa",
        })

        self._update("dangKy", "id", dang_ky["id"], {
            "trangThai": "daTaoHopDong",
            "capNhatLuc": now_iso(),
        })

        return {
            "hopDongThue": hop_dong,
            "tienCoc": tien_coc,
        }

    def khoa_coc(self, hop_dong_id: str):
        hop_dong = self._one("hopDongThue", id=hop_dong_id)
        tien_coc = self._one("tienCoc", hopDongThueId=hop_dong_id)

        tx = self.node.make_tx(
            loai_giao_dich="LOCK_DEPOSIT",
            vi_gui=hop_dong["viNguoiThue"],
            vi_nhan=SYSTEM_ESCROW_ADDRESS,
            so_tien=float(tien_coc["tongHoaCoc"]),
            du_lieu_goc={
                "hopDongThueId": hop_dong["id"],
                "tienCocId": tien_coc["id"],
                "hanhDong": "khoaCoc",
            },
        )

        block = self.node.mine_block([tx])
        self._mirror_block_to_supabase(block)

        self._update("tienCoc", "id", tien_coc["id"], {
            "soTienKhoaCoc": tien_coc["tongHoaCoc"],
            "maGiaoDichKhoaCoc": tx["maGiaoDich"],
            "heThongXuLy": True,
            "trangThai": "daKhoa",
            "capNhatLuc": now_iso(),
        })

        self._update("hopDongThue", "id", hop_dong["id"], {
            "trangThai": "dangThue",
            "maGiaoDichTao": tx["maGiaoDich"],
            "soKhoiTao": block["soKhoi"],
            "capNhatLuc": now_iso(),
        })

        return {
            "block": block,
            "transaction": tx,
        }

    def tat_toan_hop_dong(self, hop_dong_id: str, tong_tien_thanh_toan: float, tong_tien_hoan_lai: float):
        hop_dong = self._one("hopDongThue", id=hop_dong_id)
        tien_coc = self._one("tienCoc", hopDongThueId=hop_dong_id)

        tx_payment = self.node.make_tx(
            loai_giao_dich="SETTLE_PAYMENT",
            vi_gui=hop_dong["viNguoiThue"],
            vi_nhan=hop_dong["viChuXe"],
            so_tien=tong_tien_thanh_toan,
            du_lieu_goc={
                "hopDongThueId": hop_dong["id"],
                "tienCocId": tien_coc["id"],
                "hanhDong": "tatToan",
            },
        )

        txs = [tx_payment]

        if tong_tien_hoan_lai > 0:
            tx_refund = self.node.make_tx(
                loai_giao_dich="REFUND_DEPOSIT",
                vi_gui=SYSTEM_ESCROW_ADDRESS,
                vi_nhan=hop_dong["viNguoiThue"],
                so_tien=tong_tien_hoan_lai,
                du_lieu_goc={
                    "hopDongThueId": hop_dong["id"],
                    "tienCocId": tien_coc["id"],
                    "hanhDong": "hoanCoc",
                },
            )
            txs.append(tx_refund)

        block = self.node.mine_block(txs)
        self._mirror_block_to_supabase(block)

        self._update("hopDongThue", "id", hop_dong["id"], {
            "trangThai": "hoanThanh",
            "tongTienThanhToan": tong_tien_thanh_toan,
            "tongTienHoanLai": tong_tien_hoan_lai,
            "maGiaoDichTatToan": tx_payment["maGiaoDich"],
            "soKhoiTatToan": block["soKhoi"],
            "daNhanLaiXe": True,
            "capNhatLuc": now_iso(),
        })

        self._update("tienCoc", "id", tien_coc["id"], {
            "soTienHoanCoc": tong_tien_hoan_lai,
            "maGiaoDichHoanCoc": txs[1]["maGiaoDich"] if len(txs) > 1 else None,
            "heThongXuLy": True,
            "trangThai": "daTatToan" if tong_tien_hoan_lai == 0 else "daHoan",
            "capNhatLuc": now_iso(),
        })

        return {
            "block": block,
            "transactions": txs,
        }

    def xem_chain_local(self):
        return self.node.export_chain()
