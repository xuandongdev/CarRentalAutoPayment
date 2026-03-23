import json
import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ConfigDict
from supabase import create_client, Client

load_dotenv(Path(__file__).resolve().with_name(".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
NODE_DATA_DIR = os.getenv("NODE_DATA_DIR", "./NodeData")
SYSTEM_ESCROW_ADDRESS = os.getenv("SYSTEM_ESCROW_ADDRESS", "0xSYSTEMESCROW")

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
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_obj(data: Any) -> str:
    return sha256_text(stable_json(data))


def calc_merkle_root(tx_ids: list[str]) -> str:
    if not tx_ids:
        return sha256_text("EMPTY")
    hashes = [sha256_text(x) for x in tx_ids]
    while len(hashes) > 1:
        if len(hashes) % 2 == 1:
            hashes.append(hashes[-1])
        hashes = [sha256_text(hashes[i] + hashes[i + 1]) for i in range(0, len(hashes), 2)]
    return hashes[0]


class LocalNodeStorage:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.blocks_dir = self.root_dir / "Blocks"
        self.state_dir = self.root_dir / "State"
        self.transaction_index_dir = self.root_dir / "TransactionIndex"
        self.meta_dir = self.root_dir / "Meta"
        self.meta_file = self.root_dir / "meta.json"

        self.blocks_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.transaction_index_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self._init_meta_if_needed()

    def _init_meta_if_needed(self):
        if self.meta_file.exists():
            return

        genesis = {
            "blockHeight": 0,
            "timestamp": now_iso(),
            "previousHash": "0" * 64,
            "nonce": 0,
            "merkleRoot": sha256_text("GENESIS"),
            "transactionCount": 0,
            "transactions": [],
        }
        genesis["hash"] = sha256_obj(genesis)

        self._write_block(genesis)
        self._save_meta({
            "chainId": "carRentalAutoPayment",
            "latestBlockHeight": 0,
            "latestBlockHash": genesis["hash"],
            "createdAt": now_iso(),
        })

    def _save_meta(self, meta: dict):
        text = json.dumps(meta, ensure_ascii=False, indent=2)
        self.meta_file.write_text(text, encoding="utf-8")
        (self.meta_dir / "latestMeta.json").write_text(text, encoding="utf-8")

    def _load_meta(self) -> dict:
        return json.loads(self.meta_file.read_text(encoding="utf-8"))

    def _write_block(self, block: dict):
        file_path = self.blocks_dir / f"{int(block['blockHeight']):06d}.json"
        file_path.write_text(json.dumps(block, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_tx_index(self, txs: list[dict]):
        for tx in txs:
            index_path = self.transaction_index_dir / f"{tx['txHash']}.json"
            index_path.write_text(
                json.dumps({
                    "txHash": tx["txHash"],
                    "blockHeight": tx.get("blockHeight"),
                    "blockHash": tx.get("blockHash"),
                    "txIndex": tx.get("txIndex"),
                    "txType": tx.get("txType"),
                }, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

    def _write_state_snapshot(self, block: dict):
        state_path = self.state_dir / "latest.json"
        snapshot = {
            "latestBlockHeight": block["blockHeight"],
            "latestBlockHash": block["hash"],
            "updatedAt": now_iso(),
        }
        state_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    def make_tx(
        self,
        tx_type: str,
        from_address: Optional[str],
        to_address: Optional[str],
        amount: float,
        raw_data: Optional[dict] = None,
    ) -> dict:
        raw_data = raw_data or {}
        return {
            "txHash": f"TX{uuid4().hex[:12].upper()}",
            "txType": tx_type,
            "dataHash": sha256_obj(raw_data),
            "fromAddress": from_address,
            "toAddress": to_address,
            "amount": float(amount),
            "timestamp": now_iso(),
            "signature": sha256_text((from_address or "SYSTEM") + "|" + tx_type + "|" + stable_json(raw_data)),
            "status": "confirmed",
            "rawData": raw_data,
        }

    def mine_block(self, txs: list[dict]) -> dict:
        meta = self._load_meta()
        latest_height = int(meta["latestBlockHeight"])
        latest_hash = meta["latestBlockHash"]
        block_height = latest_height + 1

        merkle_root = calc_merkle_root([tx["txHash"] for tx in txs])
        block = {
            "blockHeight": block_height,
            "timestamp": now_iso(),
            "previousHash": latest_hash,
            "nonce": 0,
            "merkleRoot": merkle_root,
            "transactionCount": len(txs),
            "transactions": txs,
        }
        block["hash"] = sha256_obj({
            "blockHeight": block["blockHeight"],
            "timestamp": block["timestamp"],
            "previousHash": block["previousHash"],
            "nonce": block["nonce"],
            "merkleRoot": block["merkleRoot"],
            "transactionCount": block["transactionCount"],
            "txHashes": [tx["txHash"] for tx in txs],
        })

        for idx, tx in enumerate(block["transactions"]):
            tx["blockHeight"] = block["blockHeight"]
            tx["blockHash"] = block["hash"]
            tx["txIndex"] = idx
            tx["status"] = "confirmed"

        self._write_block(block)
        self._write_tx_index(block["transactions"])
        self._write_state_snapshot(block)
        self._save_meta({
            **meta,
            "latestBlockHeight": block_height,
            "latestBlockHash": block["hash"],
            "updatedAt": now_iso(),
        })
        return block

    def export_chain(self) -> dict:
        blocks = []
        for file_name in sorted(os.listdir(self.blocks_dir)):
            if file_name.endswith(".json"):
                blocks.append(json.loads((self.blocks_dir / file_name).read_text(encoding="utf-8")))
        return {"meta": self._load_meta(), "blocks": blocks}


class AddVehicleRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    owneremail: str = Field(alias="ownerEmail")
    bienso: str = Field(alias="bienSo")
    hangxe: str = Field(alias="hangXe")
    dongxe: str = Field(alias="dongXe")
    loaixe: str = Field(default="Sedan", alias="loaiXe")
    giatheongay: float = Field(default=0, alias="giaTheoNgay")
    giatheogio: float = Field(default=0, alias="giaTheoGio")
    namsanxuat: Optional[int] = Field(default=None, alias="namSanXuat")
    mota: Optional[str] = Field(default=None, alias="moTa")


class CreateBookingRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    renteremail: str = Field(alias="renterEmail")
    bienso: str = Field(alias="bienSo")
    songaythue: int = Field(default=1, alias="soNgayThue")
    diadiemnhan: str = Field(alias="diaDiemNhan")
    tongtienthue: float = Field(alias="tongTienThue")
    ghichu: Optional[str] = Field(default=None, alias="ghiChu")


class CreateContractRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    dangkyid: str = Field(alias="dangKyId")
    tongtiencoc: float = Field(alias="tongTienCoc")


class SettleContractRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tongtienthanhtoan: float = Field(alias="tongTienThanhToan")
    tongtienhoanlai: float = Field(default=0, alias="tongTienHoanLai")


class RentalAppService:
    def __init__(self, supabase_client: Client, node_storage: LocalNodeStorage):
        self.supabase = supabase_client
        self.node = node_storage

    def t(self, key: str):
        return self.supabase.table(TABLES[key])

    def one(self, table_key: str, **filters) -> dict:
        query = self.t(table_key).select("*")
        for k, v in filters.items():
            query = query.eq(k, v)
        result = query.limit(1).execute()
        if not result.data:
            raise ValueError(f"Khong tim thay du lieu trong bang {TABLES[table_key]} voi {filters}")
        return result.data[0]

    def maybe_one(self, table_key: str, **filters) -> Optional[dict]:
        query = self.t(table_key).select("*")
        for k, v in filters.items():
            query = query.eq(k, v)
        result = query.limit(1).execute()
        return result.data[0] if result.data else None

    def insert(self, table_key: str, payload: dict) -> dict:
        result = self.t(table_key).insert(payload).execute()
        if not result.data:
            raise ValueError(f"Insert vao {TABLES[table_key]} khong tra ve du lieu")
        return result.data[0]

    def update(self, table_key: str, match_field: str, match_value: Any, payload: dict) -> dict:
        result = self.t(table_key).update(payload).eq(match_field, match_value).execute()
        if not result.data:
            raise ValueError(f"Update {TABLES[table_key]} that bai")
        return result.data[0]

    def add_vehicle(self, req: AddVehicleRequest) -> dict:
        owner = self.one("users", email=req.owneremail)
        existed = self.maybe_one("vehicles", bienso=req.bienso)
        if existed:
            raise ValueError("Bien so da ton tai")

        return self.insert("vehicles", {
            "chuxeid": owner["id"],
            "bienso": req.bienso,
            "namsanxuat": req.namsanxuat,
            "mota": req.mota or f"{req.hangxe} {req.dongxe}",
            "hangxe": req.hangxe,
            "dongxe": req.dongxe,
            "loaixe": req.loaixe,
            "trangthai": "sanSang",
            "giatheongay": req.giatheongay,
            "giatheogio": req.giatheogio,
            "baohiem": "Chua cap nhat",
            "dangkiem": "Chua cap nhat",
            "dangkyxe": "Chua cap nhat",
        })

    def create_booking(self, req: CreateBookingRequest) -> dict:
        renter = self.one("users", email=req.renteremail)
        vehicle = self.one("vehicles", bienso=req.bienso)
        return self.insert("bookings", {
            "nguoidungid": renter["id"],
            "xeid": vehicle["id"],
            "songaythue": req.songaythue,
            "diadiemnhan": req.diadiemnhan,
            "tongtienthue": req.tongtienthue,
            "trangthai": "daDuyet",
            "ghichu": req.ghichu or "Tao tu UI demo",
        })

    def create_contract_from_booking(self, req: CreateContractRequest) -> dict:
        booking = self.one("bookings", id=req.dangkyid)
        existed = self.maybe_one("contracts", dangkyid=req.dangkyid)
        if existed:
            raise ValueError("Dang ky nay da co hop dong")

        vehicle = self.one("vehicles", id=booking["xeid"])
        renter = self.one("users", id=booking["nguoidungid"])
        owner = self.one("users", id=vehicle["chuxeid"])
        renter_wallet = self.one("wallets", nguoidungid=renter["id"])
        owner_wallet = self.one("wallets", nguoidungid=owner["id"])

        contract_hash = sha256_obj({
            "bookingId": booking["id"],
            "xeId": vehicle["id"],
            "nguoiThueId": renter["id"],
            "chuXeId": owner["id"],
            "tongTienCoc": req.tongtiencoc,
            "createdAt": now_iso(),
        })

        contract = self.insert("contracts", {
            "dangkyid": booking["id"],
            "xeid": vehicle["id"],
            "nguoithueid": renter["id"],
            "chuxeid": owner["id"],
            "addressnguoithue": renter_wallet["address"],
            "addresschuxe": owner_wallet["address"],
            "contracthash": contract_hash,
            "signaturenguoithue": sha256_text("sign|renter|" + contract_hash),
            "signaturechuxe": sha256_text("sign|owner|" + contract_hash),
            "trangthai": "khoiTao",
            "tongtiencoc": req.tongtiencoc,
            "tongtienthanhtoan": 0,
            "tongtienhoanlai": 0,
            "dagiaoxe": False,
            "danhanlaixe": False,
        })

        deposit = self.insert("deposits", {
            "hopdongthueid": contract["id"],
            "tonghoacoc": req.tongtiencoc,
            "thoathuancoc": "Dat coc truoc khi nhan xe",
            "sotienkhoacoc": 0,
            "sotienhoancoc": 0,
            "hethongxuly": False,
            "trangthai": "chuaKhoa",
        })

        self.update("bookings", "id", booking["id"], {
            "trangthai": "daTaoHopDong",
            "capnhatluc": now_iso(),
        })

        return {"hopDongThue": contract, "tienCoc": deposit}

    def mirror_block(self, block: dict):
        self.insert("blocks", {
            "blockheight": block["blockHeight"],
            "timestamp": block["timestamp"],
            "previoushash": block["previousHash"],
            "hash": block["hash"],
            "nonce": block["nonce"],
            "merkleroot": block["merkleRoot"],
            "transactioncount": block["transactionCount"],
            "rawdata": block,
        })

        for tx in block["transactions"]:
            tx_row = self.insert("transactions", {
                "txhash": tx["txHash"],
                "txtype": tx["txType"],
                "datahash": tx["dataHash"],
                "fromaddress": tx.get("fromAddress"),
                "toaddress": tx.get("toAddress"),
                "amount": tx["amount"],
                "timestamp": tx["timestamp"],
                "signature": tx["signature"],
                "status": tx["status"],
                "blockheight": tx["blockHeight"],
                "blockhash": tx["blockHash"],
                "hopdongthueid": tx["rawData"].get("hopDongThueId"),
                "tiencocid": tx["rawData"].get("tienCocId"),
                "tranhchapid": tx["rawData"].get("tranhChapId"),
                "rawdata": tx,
            })

            self.insert("events", {
                "eventid": f"EV{uuid4().hex[:12].upper()}",
                "txhash": tx_row["txhash"],
                "eventname": tx["txType"] + "Confirmed",
                "blockheight": block["blockHeight"],
                "blockhash": block["hash"],
                "data": {
                    "hopDongThueId": tx["rawData"].get("hopDongThueId"),
                    "amount": tx["amount"],
                    "from": tx.get("fromAddress"),
                    "to": tx.get("toAddress"),
                },
            })

    def lock_deposit(self, contract_id: str) -> dict:
        contract = self.one("contracts", id=contract_id)
        deposit = self.one("deposits", hopdongthueid=contract_id)

        tx = self.node.make_tx(
            tx_type="LOCK_DEPOSIT",
            from_address=contract["addressnguoithue"],
            to_address=SYSTEM_ESCROW_ADDRESS,
            amount=float(deposit["tonghoacoc"]),
            raw_data={
                "hopDongThueId": contract_id,
                "tienCocId": deposit["id"],
                "action": "khoaCoc",
            },
        )

        block = self.node.mine_block([tx])
        self.mirror_block(block)

        self.update("deposits", "id", deposit["id"], {
            "sotienkhoacoc": deposit["tonghoacoc"],
            "txhashlock": tx["txHash"],
            "hethongxuly": True,
            "trangthai": "daKhoa",
        })

        self.update("contracts", "id", contract_id, {
            "trangthai": "dangThue",
            "txhashcreate": tx["txHash"],
            "blocknumbercreate": block["blockHeight"],
            "dagiaoxe": True,
        })

        return {"block": block, "transaction": tx}

    def settle_contract(self, contract_id: str, tong_tien_thanh_toan: float, tong_tien_hoan_lai: float) -> dict:
        contract = self.one("contracts", id=contract_id)
        deposit = self.one("deposits", hopdongthueid=contract_id)

        txs = [
            self.node.make_tx(
                tx_type="SETTLE_PAYMENT",
                from_address=contract["addressnguoithue"],
                to_address=contract["addresschuxe"],
                amount=tong_tien_thanh_toan,
                raw_data={
                    "hopDongThueId": contract_id,
                    "tienCocId": deposit["id"],
                    "action": "tatToan",
                },
            )
        ]

        refund_tx = None
        if tong_tien_hoan_lai > 0:
            refund_tx = self.node.make_tx(
                tx_type="REFUND_DEPOSIT",
                from_address=SYSTEM_ESCROW_ADDRESS,
                to_address=contract["addressnguoithue"],
                amount=tong_tien_hoan_lai,
                raw_data={
                    "hopDongThueId": contract_id,
                    "tienCocId": deposit["id"],
                    "action": "hoanCoc",
                },
            )
            txs.append(refund_tx)

        block = self.node.mine_block(txs)
        self.mirror_block(block)

        self.update("contracts", "id", contract_id, {
            "trangthai": "hoanThanh",
            "tongtienthanhtoan": tong_tien_thanh_toan,
            "tongtienhoanlai": tong_tien_hoan_lai,
            "txhashsettlement": txs[0]["txHash"],
            "blocknumbersettlement": block["blockHeight"],
            "danhanlaixe": True,
        })

        self.update("deposits", "id", deposit["id"], {
            "sotienhoancoc": tong_tien_hoan_lai,
            "txhashrefund": refund_tx["txHash"] if refund_tx else None,
            "hethongxuly": True,
            "trangthai": "daHoan" if tong_tien_hoan_lai > 0 else "daTatToan",
        })

        return {"block": block, "transactions": txs}

    def overview(self) -> dict:
        vehicles = self.t("vehicles").select("*").limit(10).execute().data
        bookings = self.t("bookings").select("*").limit(10).execute().data
        contracts = self.t("contracts").select("*").limit(10).execute().data
        transactions = self.t("transactions").select("*").limit(10).execute().data
        return {
            "vehicles": vehicles,
            "bookings": bookings,
            "contracts": contracts,
            "transactions": transactions,
            "chain": self.node.export_chain(),
        }


app = FastAPI(title="Car Rental Demo Server", version="1.0.0")

if not SUPABASE_URL or not SUPABASE_KEY:
    supabase: Optional[Client] = None
else:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

node_storage = LocalNodeStorage(NODE_DATA_DIR)
service = RentalAppService(supabase, node_storage) if supabase else None


def require_service() -> RentalAppService:
    if service is None:
        raise HTTPException(status_code=500, detail="Thieu SUPABASE_URL hoac SUPABASE_KEY trong .env")
    return service


HTML_PAGE = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Car Rental Demo</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f5f6f8; margin:0; padding:24px; }
    .wrap { max-width: 1200px; margin: 0 auto; }
    h1 { margin-top:0; }
    .grid { display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:16px; }
    .card { background:white; border-radius:14px; padding:16px; box-shadow:0 1px 3px rgba(0,0,0,.08); }
    label { display:block; font-size:14px; margin-top:8px; color:#333; }
    input, button, textarea { width:100%; box-sizing:border-box; padding:10px 12px; margin-top:6px; border:1px solid #d0d5dd; border-radius:10px; }
    button { cursor:pointer; background:#111827; color:white; border:none; font-weight:600; }
    button.secondary { background:#2563eb; }
    pre { background:#0f172a; color:#e2e8f0; padding:12px; border-radius:10px; overflow:auto; max-height:360px; }
    .section { margin-top:16px; }
    .muted { color:#666; font-size:13px; }
    @media (max-width: 900px) { .grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Demo thao tac thue xe + giao dich blockchain</h1>
    <p class="muted">UI don gian goi fetch ve backend. Backend doc/ghi Supabase va mine block local trong thu muc NodeData.</p>

    <div class="grid">
      <div class="card">
        <h3>1. Them xe</h3>
        <label>Email chu xe <input id="ownerEmail" value="chuxe1@example.com"></label>
        <label>Bien so <input id="bienSo" value="51A-99999"></label>
        <label>Hang xe <input id="hangXe" value="Toyota"></label>
        <label>Dong xe <input id="dongXe" value="Vios"></label>
        <label>Loai xe <input id="loaiXe" value="Sedan"></label>
        <label>Gia theo ngay <input id="giaTheoNgay" value="800000"></label>
        <label>Gia theo gio <input id="giaTheoGio" value="120000"></label>
        <button onclick="addVehicle()">Them xe</button>
      </div>

      <div class="card">
        <h3>2. Tao dang ky thue xe</h3>
        <label>Email nguoi thue <input id="renterEmail" value="khach1@example.com"></label>
        <label>Bien so xe <input id="bookingBienSo" value="51A-99999"></label>
        <label>So ngay thue <input id="soNgayThue" value="2"></label>
        <label>Dia diem nhan <input id="diaDiemNhan" value="Regent Phu Quoc"></label>
        <label>Tong tien thue <input id="tongTienThue" value="1600000"></label>
        <button onclick="createBooking()">Tao dang ky</button>
      </div>

      <div class="card">
        <h3>3. Tao hop dong tu dang ky</h3>
        <label>Dang ky ID <input id="dangKyId" placeholder="copy tu ket qua o duoi"></label>
        <label>Tong tien coc <input id="tongTienCoc" value="2000000"></label>
        <button class="secondary" onclick="createContract()">Tao hop dong</button>
      </div>

      <div class="card">
        <h3>4. Khoa coc</h3>
        <label>Hop dong ID <input id="hopDongIdLock" placeholder="copy tu ket qua o duoi"></label>
        <button onclick="lockDeposit()">Khoa coc va mine block</button>
      </div>

      <div class="card">
        <h3>5. Tat toan hop dong</h3>
        <label>Hop dong ID <input id="hopDongIdSettle" placeholder="copy tu ket qua o duoi"></label>
        <label>Tong tien thanh toan <input id="tongTienThanhToan" value="1500000"></label>
        <label>Tong tien hoan lai <input id="tongTienHoanLai" value="500000"></label>
        <button onclick="settleContract()">Tat toan va mine block</button>
      </div>

      <div class="card">
        <h3>6. Tai lai du lieu</h3>
        <button class="secondary" onclick="refreshData()">Refresh overview</button>
      </div>
    </div>

    <div class="section card">
      <h3>Ket qua</h3>
      <pre id="result">Chua co du lieu</pre>
    </div>

    <div class="section card">
      <h3>Overview</h3>
      <pre id="overview">Dang tai...</pre>
    </div>
  </div>

<script>
async function api(url, method='GET', body=null) {
  const res = await fetch(url, {
    method,
    headers: {'Content-Type':'application/json'},
    body: body ? JSON.stringify(body) : null
  });

  const data = await res.json();

  if (!res.ok) {
    const detail =
      typeof data.detail === 'string'
        ? data.detail
        : JSON.stringify(data.detail ?? data, null, 2);

    throw new Error(detail);
  }

  return data;
}

function showResult(data) {
  document.getElementById('result').textContent =
    typeof data === 'string' ? data : JSON.stringify(data, null, 2);
}

async function refreshData() {
  try {
    const data = await api('/api/overview');
    document.getElementById('overview').textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById('overview').textContent = e.message;
  }
}

async function addVehicle() {
  try {
    const data = await api('/api/vehicles', 'POST', {
      ownerEmail: document.getElementById('ownerEmail').value,
      bienSo: document.getElementById('bienSo').value,
      hangXe: document.getElementById('hangXe').value,
      dongXe: document.getElementById('dongXe').value,
      loaiXe: document.getElementById('loaiXe').value,
      giaTheoNgay: Number(document.getElementById('giaTheoNgay').value),
      giaTheoGio: Number(document.getElementById('giaTheoGio').value),
    });
    showResult(data);
    await refreshData();
  } catch (e) { showResult({error:e.message}); }
}

async function createBooking() {
  try {
    const data = await api('/api/bookings', 'POST', {
      renterEmail: document.getElementById('renterEmail').value,
      bienSo: document.getElementById('bookingBienSo').value,
      soNgayThue: Number(document.getElementById('soNgayThue').value),
      diaDiemNhan: document.getElementById('diaDiemNhan').value,
      tongTienThue: Number(document.getElementById('tongTienThue').value),
    });
    showResult(data);
    if (data.id) document.getElementById('dangKyId').value = data.id;
    await refreshData();
  } catch (e) { showResult({error:e.message}); }
}

async function createContract() {
  try {
    const data = await api('/api/contracts/from-booking', 'POST', {
      dangKyId: document.getElementById('dangKyId').value,
      tongTienCoc: Number(document.getElementById('tongTienCoc').value),
    });
    showResult(data);
    if (data.hopDongThue && data.hopDongThue.id) {
      document.getElementById('hopDongIdLock').value = data.hopDongThue.id;
      document.getElementById('hopDongIdSettle').value = data.hopDongThue.id;
    }
    await refreshData();
  } catch (e) { showResult({error:e.message}); }
}

async function lockDeposit() {
  try {
    const id = document.getElementById('hopDongIdLock').value;
    const data = await api(`/api/contracts/${id}/lock-deposit`, 'POST');
    showResult(data);
    await refreshData();
  } catch (e) { showResult({error:e.message}); }
}

async function settleContract() {
  try {
    const id = document.getElementById('hopDongIdSettle').value;
    const data = await api(`/api/contracts/${id}/settle`, 'POST', {
      tongTienThanhToan: Number(document.getElementById('tongTienThanhToan').value),
      tongTienHoanLai: Number(document.getElementById('tongTienHoanLai').value),
    });
    showResult(data);
    await refreshData();
  } catch (e) { showResult({error:e.message}); }
}

refreshData();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE


@app.get("/api/overview")
def api_overview():
    try:
        return require_service().overview()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/node/chain")
def api_chain():
    return node_storage.export_chain()


@app.post("/api/vehicles")
def api_add_vehicle(req: AddVehicleRequest):
    try:
        return require_service().add_vehicle(req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/bookings")
def api_create_booking(req: CreateBookingRequest):
    try:
        return require_service().create_booking(req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/contracts/from-booking")
def api_create_contract(req: CreateContractRequest):
    try:
        return require_service().create_contract_from_booking(req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/contracts/{contract_id}/lock-deposit")
def api_lock_deposit(contract_id: str):
    try:
        return require_service().lock_deposit(contract_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)