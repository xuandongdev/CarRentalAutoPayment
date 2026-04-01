from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from .Service.RentalService import RentalService
except ImportError:
    from Service.RentalService import RentalService

app = FastAPI(title="Car Rental Auto Payment Demo Backend")

service = RentalService()


class TaoHopDongRequest(BaseModel):
    dangKyId: str
    tongTienCoc: float


class TatToanRequest(BaseModel):
    tongTienThanhToan: float
    tongTienHoanLai: float


@app.get("/")
def root():
    return {
        "message": "Backend demo dang chay",
        "flow": [
            "tao hop dong tu dang ky",
            "khoa coc",
            "tat toan hop dong",
            "xem chain local",
        ]
    }


@app.post("/hop-dong/tao-tu-dang-ky")
def tao_hop_dong(req: TaoHopDongRequest):
    try:
        return service.tao_hop_dong_tu_dang_ky(req.dangKyId, req.tongTienCoc)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/hop-dong/{hop_dong_id}/khoa-coc")
def khoa_coc(hop_dong_id: str):
    try:
        return service.khoa_coc(hop_dong_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/hop-dong/{hop_dong_id}/tat-toan")
def tat_toan(hop_dong_id: str, req: TatToanRequest):
    try:
        return service.tat_toan_hop_dong(
            hop_dong_id=hop_dong_id,
            tong_tien_thanh_toan=req.tongTienThanhToan,
            tong_tien_hoan_lai=req.tongTienHoanLai,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/node/chain")
def xem_chain():
    try:
        return service.xem_chain_local()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
