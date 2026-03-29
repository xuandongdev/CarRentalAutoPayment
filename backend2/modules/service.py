
from typing import Any, Optional

from supabase import Client

from .config import (
    CONTRACT_STATUS_ALIASES,
    CONTRACT_STATUS_DB,
    DEPOSIT_STATUS_ALIASES,
    DEPOSIT_STATUS_DB,
    DISPUTE_STATUS_ALIASES,
    DISPUTE_STATUS_DB,
    SYSTEM_ESCROW_ADDRESS,
    TABLES,
    TX_EVENT_NAMES,
)
from .models import (
    AddVehicleRequest,
    AdminConfirmDamageRequest,
    AdminConfirmNoDamageRequest,
    CreateBookingRequest,
    CreateContractRequest,
    CreateDamageClaimRequest,
    ReturnVehicleRequest,
)
from .node_storage import LocalNodeStorage
from .utils import now_iso, sha256_obj, sha256_text


class RentalAppService:
    def __init__(self, supabase_client: Client, node_storage: LocalNodeStorage):
        self.supabase = supabase_client
        self.node = node_storage

    def t(self, key: str):
        return self.supabase.table(TABLES[key])

    def one(self, table_key: str, **filters) -> dict:
        query = self.t(table_key).select("*")
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.limit(1).execute()
        if not result.data:
            raise ValueError(f"Khong tim thay du lieu trong bang {TABLES[table_key]} voi {filters}")
        return result.data[0]

    def maybe_one(self, table_key: str, **filters) -> Optional[dict]:
        query = self.t(table_key).select("*")
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.limit(1).execute()
        return result.data[0] if result.data else None

    def list_rows(self, table_key: str, limit: int = 10) -> list[dict]:
        return self.t(table_key).select("*").limit(limit).execute().data or []

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

    def _event_name_for_tx(self, tx_type: str) -> str:
        return TX_EVENT_NAMES.get(tx_type, tx_type.lower())

    def _build_evidence_hash(self, action: str, payload: dict[str, Any]) -> str:
        return sha256_obj({"action": action, "payload": payload})

    def _allowed_statuses(self, aliases: dict[str, set[str]], names: list[str]) -> set[str]:
        allowed = set()
        for name in names:
            allowed |= aliases.get(name, {name})
        return allowed

    def _db_status(self, mapping: dict[str, str], logical_status: str) -> str:
        return mapping.get(logical_status, logical_status)

    def _ensure_contract_status(self, contract: dict, allowed_statuses: list[str], action: str):
        status = contract.get("trangthai")
        if status == self._db_status(CONTRACT_STATUS_DB, "hoanThanh"):
            raise ValueError("Contract da hoan thanh, khong the xu ly lai")
        if status not in self._allowed_statuses(CONTRACT_STATUS_ALIASES, allowed_statuses):
            raise ValueError(f"Khong the {action} khi contract dang o trang thai {status}")

    def _ensure_dispute_status(self, dispute: dict, allowed_statuses: list[str], action: str):
        status = dispute.get("trangthai")
        if status not in self._allowed_statuses(DISPUTE_STATUS_ALIASES, allowed_statuses):
            raise ValueError(f"Khong the {action} khi tranh chap dang o trang thai {status}")

    def _get_contract_and_deposit(self, contract_id: str) -> tuple[dict, dict]:
        return self.one("contracts", id=contract_id), self.one("deposits", hopdongthueid=contract_id)

    def _latest_damage_report(self, contract_id: str) -> Optional[dict]:
        result = self.t("damage_reports").select("*").eq("hopdongthueid", contract_id).order("taoluc", desc=True).limit(1).execute()
        return result.data[0] if result.data else None

    def _get_dispute_bundle(self, dispute_id: str) -> tuple[dict, dict, dict, Optional[dict]]:
        dispute = self.one("disputes", id=dispute_id)
        contract, deposit = self._get_contract_and_deposit(dispute["hopdongthueid"])
        report = self._latest_damage_report(contract["id"])
        return dispute, contract, deposit, report

    def _has_open_dispute(self, contract_id: str) -> bool:
        rows = self.t("disputes").select("id,trangthai").eq("hopdongthueid", contract_id).limit(20).execute().data or []
        open_statuses = self._allowed_statuses(DISPUTE_STATUS_ALIASES, ["moiTao", "choAdminXacMinh"])
        return any((row.get("trangthai") in open_statuses) for row in rows)

    def _locked_deposit_amount(self, deposit: dict) -> float:
        amount = float(deposit.get("sotienkhoacoc") or 0)
        return amount if amount > 0 else float(deposit.get("tonghoacoc") or 0)

    def _ensure_admin_user_context(self, admin_id: str) -> dict:
        admin = self.one("users", id=admin_id)
        role = admin.get("vaitro") or admin.get("role") or admin.get("loainguoidung") or admin.get("userrole")
        if role is not None and str(role).lower() not in {"admin", "quantri"}:
            raise ValueError("Nguoi xu ly khong co quyen admin")
        return admin

    def _get_wallet_by_user_id(self, user_id: str) -> Optional[dict]:
        return self.maybe_one("wallets", nguoidungid=user_id)

    def _require_user_wallet(self, user_id: str, context: str) -> dict:
        wallet = self._get_wallet_by_user_id(user_id)
        if wallet is None:
            raise ValueError(f"Khong tim thay vi cho {context}")
        return wallet

    def _exists_block(self, block_hash: str) -> bool:
        return self.maybe_one("blocks", hash=block_hash) is not None

    def _exists_transaction(self, tx_hash: str) -> bool:
        return self.maybe_one("transactions", txhash=tx_hash) is not None

    def _build_event_signature_key(self, tx: dict) -> str:
        raw = tx.get("rawData", {})
        event_name = self._event_name_for_tx(tx["txType"])
        parts = [
            tx["txHash"],
            event_name,
            str(raw.get("hopDongThueId") or ""),
            str(raw.get("tienCocId") or ""),
            str(raw.get("tranhChapId") or ""),
            str(raw.get("baoCaoHuHaiId") or ""),
        ]
        return f"EV{sha256_text('|'.join(parts))[:24].upper()}"

    def _exists_event(self, signature_key: str) -> bool:
        return self.maybe_one("events", eventid=signature_key) is not None

    def _mirror_event_for_tx(self, block: dict, tx_row: dict, tx: dict) -> bool:
        signature_key = self._build_event_signature_key(tx)
        if self._exists_event(signature_key):
            return False
        self.insert("events", {
            "eventid": signature_key,
            "txhash": tx_row["txhash"],
            "eventname": self._event_name_for_tx(tx["txType"]),
            "blockheight": block["blockHeight"],
            "blockhash": block["hash"],
            "data": {
                "signatureKey": signature_key,
                "hopDongThueId": tx["rawData"].get("hopDongThueId"),
                "tienCocId": tx["rawData"].get("tienCocId"),
                "tranhChapId": tx["rawData"].get("tranhChapId"),
                "baoCaoHuHaiId": tx["rawData"].get("baoCaoHuHaiId"),
                "amount": tx["amount"],
                "from": tx.get("fromAddress"),
                "to": tx.get("toAddress"),
                "decision": tx["rawData"].get("decision"),
                "evidenceHash": tx["rawData"].get("evidenceHash") or tx["rawData"].get("decisionHash"),
            },
        })
        return True

    def mirror_block(self, block: dict) -> dict:
        inserted_block = 0
        inserted_transactions = 0
        inserted_events = 0

        if not self._exists_block(block["hash"]):
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
            inserted_block = 1

        for tx in block["transactions"]:
            tx_row = self.maybe_one("transactions", txhash=tx["txHash"])
            if tx_row is None:
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
                inserted_transactions += 1
            if self._mirror_event_for_tx(block, tx_row, tx):
                inserted_events += 1

        return {
            "insertedBlock": inserted_block,
            "insertedTransactions": inserted_transactions,
            "insertedEvents": inserted_events,
        }

    def _mine_and_mirror(self, txs: list[dict]) -> dict:
        block = self.node.mine_block(txs)
        mirror_stats = self.mirror_block(block)
        return {"block": block, "mirror": mirror_stats}

    def _get_db_latest_block_meta(self) -> dict:
        result = self.t("blocks").select("blockheight,hash").order("blockheight", desc=True).limit(1).execute()
        if not result.data:
            return {"blockheight": None, "hash": None}
        return result.data[0]

    def reconcile_chain_to_db(self) -> dict:
        chain = self.node.export_chain()
        mirrored_new_blocks = 0
        mirrored_new_transactions = 0
        skipped_blocks = 0

        for block in chain.get("blocks", []):
            stats = self.mirror_block(block)
            mirrored_new_blocks += stats["insertedBlock"]
            mirrored_new_transactions += stats["insertedTransactions"]
            if stats["insertedBlock"] == 0:
                skipped_blocks += 1

        return {
            "localBlockCount": len(chain.get("blocks", [])),
            "mirroredNewBlocks": mirrored_new_blocks,
            "mirroredNewTransactions": mirrored_new_transactions,
            "skippedBlocks": skipped_blocks,
        }
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
            "taoluc": now_iso(),
            "capnhatluc": now_iso(),
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
            "taoluc": now_iso(),
            "capnhatluc": now_iso(),
        })

    def create_contract_from_booking(self, req: CreateContractRequest) -> dict:
        booking = self.one("bookings", id=req.dangkyid)
        existed = self.maybe_one("contracts", dangkyid=req.dangkyid)
        if existed:
            raise ValueError("Dang ky nay da co hop dong")
        vehicle = self.one("vehicles", id=booking["xeid"])
        renter = self.one("users", id=booking["nguoidungid"])
        owner = self.one("users", id=vehicle["chuxeid"])
        renter_wallet = self._require_user_wallet(renter["id"], "nguoi thue")
        owner_wallet = self._require_user_wallet(owner["id"], "chu xe")
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
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "khoiTao"),
            "tongtiencoc": req.tongtiencoc,
            "tongtienthanhtoan": 0,
            "tongtienhoanlai": 0,
            "dagiaoxe": False,
            "danhanlaixe": False,
            "summaryhash": contract_hash,
            "taoluc": now_iso(),
            "capnhatluc": now_iso(),
        })
        deposit = self.insert("deposits", {
            "hopdongthueid": contract["id"],
            "tonghoacoc": req.tongtiencoc,
            "thoathuancoc": "Dat coc truoc khi nhan xe",
            "sotienkhoacoc": 0,
            "sotienhoancoc": 0,
            "txhashlock": None,
            "txhashrefund": None,
            "hethongxuly": False,
            "trangthai": self._db_status(DEPOSIT_STATUS_DB, "chuaKhoa"),
            "taoluc": now_iso(),
            "capnhatluc": now_iso(),
        })
        self.update("bookings", "id", booking["id"], {"trangthai": "daTaoHopDong", "capnhatluc": now_iso()})
        return {"hopDongThue": contract, "tienCoc": deposit}

    def lock_deposit(self, contract_id: str) -> dict:
        contract, deposit = self._get_contract_and_deposit(contract_id)
        self._ensure_contract_status(contract, ["khoiTao", "choKhoaCoc"], "khoa coc")
        if deposit.get("trangthai") not in self._allowed_statuses(DEPOSIT_STATUS_ALIASES, ["chuaKhoa"]):
            raise ValueError("Tien coc da duoc xu ly, khong the khoa lai")
        tx = self.node.make_tx(
            "LOCK_DEPOSIT",
            contract["addressnguoithue"],
            SYSTEM_ESCROW_ADDRESS,
            float(deposit["tonghoacoc"]),
            {"hopDongThueId": contract_id, "tienCocId": deposit["id"], "action": "khoaCoc"},
        )
        mine_result = self._mine_and_mirror([tx])
        block = mine_result["block"]
        deposit = self.update("deposits", "id", deposit["id"], {
            "sotienkhoacoc": deposit["tonghoacoc"],
            "txhashlock": tx["txHash"],
            "hethongxuly": True,
            "trangthai": self._db_status(DEPOSIT_STATUS_DB, "daKhoa"),
            "capnhatluc": now_iso(),
        })
        contract = self.update("contracts", "id", contract_id, {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "dangThue"),
            "dagiaoxe": True,
            "capnhatluc": now_iso(),
        })
        return {"block": block, "transaction": tx, "hopDongThue": contract, "tienCoc": deposit, "mirror": mine_result["mirror"]}

    def return_vehicle(self, contract_id: str, req: ReturnVehicleRequest) -> dict:
        contract, deposit = self._get_contract_and_deposit(contract_id)
        self._ensure_contract_status(contract, ["dangThue"], "tra xe")
        if contract.get("danhanlaixe"):
            raise ValueError("Contract da o sau buoc tra xe, khong the tra xe lap lai")
        if req.nguoitraid != contract["nguoithueid"]:
            raise ValueError("Nguoi tra xe khong dung voi nguoi thue cua contract")
        if deposit.get("trangthai") not in self._allowed_statuses(DEPOSIT_STATUS_ALIASES, ["daKhoa"]):
            raise ValueError("Deposit chua khoa hoac khong con o trang thai cho phep tra xe")
        payload = {
            "hopDongThueId": contract_id,
            "nguoiTraId": req.nguoitraid,
            "ghiChu": req.ghichu,
            "evidenceUrls": req.evidenceurls,
            "evidenceMeta": req.evidencemeta,
        }
        evidence_hash = self._build_evidence_hash("vehicleReturned", payload)
        tx = self.node.make_tx(
            "VEHICLE_RETURNED",
            contract["addressnguoithue"],
            contract["addresschuxe"],
            0,
            {
                "hopDongThueId": contract_id,
                "tienCocId": deposit["id"],
                "action": "traXe",
                "evidenceHash": evidence_hash,
                **payload,
            },
        )
        mine_result = self._mine_and_mirror([tx])
        block = mine_result["block"]
        contract = self.update("contracts", "id", contract_id, {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "choKiemTraTraXe"),
            "danhanlaixe": True,
            "summaryhash": evidence_hash,
            "capnhatluc": now_iso(),
        })
        return {"block": block, "transaction": tx, "contract": contract, "mirror": mine_result["mirror"], "returnEvidenceHash": evidence_hash}
    def create_damage_claim(self, contract_id: str, req: CreateDamageClaimRequest) -> dict:
        contract, deposit = self._get_contract_and_deposit(contract_id)
        self._ensure_contract_status(contract, ["dangThue", "choKiemTraTraXe"], "tao khieu nai hu hai")
        if not contract.get("danhanlaixe"):
            raise ValueError("Chi duoc khieu nai sau khi xe da duoc tra")
        if req.ownerid != contract["chuxeid"]:
            raise ValueError("ownerId khong dung voi chu xe cua contract")
        if deposit.get("trangthai") not in self._allowed_statuses(DEPOSIT_STATUS_ALIASES, ["daKhoa", "tamGiuDoTranhChap"]):
            raise ValueError("Deposit chua khoa ma da tranh chap")
        if self._has_open_dispute(contract_id):
            raise ValueError("Contract nay da co tranh chap dang mo")

        payload = {
            "hopDongThueId": contract_id,
            "ownerId": req.ownerid,
            "lyDo": req.lydo,
            "estimatedCost": req.estimatedcost,
            "evidenceUrls": req.evidenceurls,
            "evidenceMeta": req.evidencemeta,
            "ghiChu": req.ghichu,
        }
        evidence_hash = self._build_evidence_hash("damageClaimed", payload)
        report = self.insert("damage_reports", {
            "hopdongthueid": contract_id,
            "mota": req.lydo,
            "chiphisua": req.estimatedcost,
            "danhsachanh": req.evidenceurls,
            "reporthash": evidence_hash,
            "trangthai": "moiTao",
            "txhashrecord": None,
            "taoluc": now_iso(),
            "capnhatluc": now_iso(),
        })
        dispute = self.insert("disputes", {
            "hopdongthueid": contract_id,
            "lydo": req.lydo,
            "loai": "damageClaim",
            "trangthai": self._db_status(DISPUTE_STATUS_DB, "choAdminXacMinh"),
            "ketquaxuly": None,
            "sotienphaithu": req.estimatedcost,
            "noidungketluan": req.ghichu or "Cho admin xac minh khieu nai hu hai",
            "txhashresolve": None,
            "taoluc": now_iso(),
            "capnhatluc": now_iso(),
        })
        tx = self.node.make_tx(
            "DAMAGE_CLAIMED",
            contract["addresschuxe"],
            SYSTEM_ESCROW_ADDRESS,
            0,
            {
                "hopDongThueId": contract_id,
                "tienCocId": deposit["id"],
                "tranhChapId": dispute["id"],
                "baoCaoHuHaiId": report["id"],
                "action": "taoKhieuNai",
                "evidenceHash": evidence_hash,
                **payload,
            },
        )
        mine_result = self._mine_and_mirror([tx])
        block = mine_result["block"]
        report = self.update("damage_reports", "id", report["id"], {
            "txhashrecord": tx["txHash"],
            "capnhatluc": now_iso(),
        })
        deposit = self.update("deposits", "id", deposit["id"], {
            "hethongxuly": True,
            "trangthai": self._db_status(DEPOSIT_STATUS_DB, "tamGiuDoTranhChap"),
            "capnhatluc": now_iso(),
        })
        contract = self.update("contracts", "id", contract_id, {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "dangTranhChap"),
            "capnhatluc": now_iso(),
        })
        dispute = self.update("disputes", "id", dispute["id"], {"capnhatluc": now_iso()})
        return {"block": block, "transaction": tx, "contract": contract, "deposit": deposit, "dispute": dispute, "damageReport": report, "mirror": mine_result["mirror"]}

    def admin_confirm_no_damage(self, dispute_id: str, req: AdminConfirmNoDamageRequest) -> dict:
        dispute, contract, deposit, report = self._get_dispute_bundle(dispute_id)
        self._ensure_dispute_status(dispute, ["choAdminXacMinh"], "xac nhan khong hu hai")
        self._ensure_admin_user_context(req.adminid)
        admin_wallet = self._require_user_wallet(req.adminid, "admin")
        locked = self._locked_deposit_amount(deposit)
        if locked <= 0:
            raise ValueError("Deposit khong con so tien dang khoa de hoan")

        payload = {
            "tranhChapId": dispute_id,
            "hopDongThueId": contract["id"],
            "adminId": req.adminid,
            "decisionNote": req.decisionnote,
            "evidenceMeta": req.evidencemeta,
            "decision": "khongCoHuHai",
        }
        decision_hash = self._build_evidence_hash("adminDecisionNoDamage", payload)
        decision_tx = self.node.make_tx(
            "ADMIN_DECISION_NO_DAMAGE",
            admin_wallet["address"],
            SYSTEM_ESCROW_ADDRESS,
            0,
            {
                "hopDongThueId": contract["id"],
                "tienCocId": deposit["id"],
                "tranhChapId": dispute_id,
                "baoCaoHuHaiId": report["id"] if report else None,
                "decision": "khongCoHuHai",
                "decisionHash": decision_hash,
                **payload,
            },
        )
        refund_tx = self.node.make_tx(
            "REFUND_DEPOSIT",
            SYSTEM_ESCROW_ADDRESS,
            contract["addressnguoithue"],
            locked,
            {
                "hopDongThueId": contract["id"],
                "tienCocId": deposit["id"],
                "tranhChapId": dispute_id,
                "action": "hoanToanBoTienCoc",
                "decision": "khongCoHuHai",
                "decisionHash": decision_hash,
            },
        )
        mine_result = self._mine_and_mirror([decision_tx, refund_tx])
        block = mine_result["block"]
        dispute = self.update("disputes", "id", dispute_id, {
            "trangthai": self._db_status(DISPUTE_STATUS_DB, "daDong"),
            "ketquaxuly": "khongCoHuHai",
            "noidungketluan": req.decisionnote,
            "txhashresolve": decision_tx["txHash"],
            "capnhatluc": now_iso(),
        })
        if report:
            report = self.update("damage_reports", "id", report["id"], {
                "trangthai": "daDong",
                "capnhatluc": now_iso(),
            })
        deposit = self.update("deposits", "id", deposit["id"], {
            "sotienhoancoc": locked,
            "sotienkhoacoc": 0,
            "txhashrefund": refund_tx["txHash"],
            "hethongxuly": True,
            "trangthai": self._db_status(DEPOSIT_STATUS_DB, "daHoan"),
            "capnhatluc": now_iso(),
        })
        contract = self.update("contracts", "id", contract["id"], {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "hoanThanh"),
            "txhashsettlement": refund_tx["txHash"],
            "blocknumbersettlement": block["blockHeight"],
            "tongtienhoanlai": locked,
            "danhanlaixe": True,
            "summaryhash": decision_hash,
            "capnhatluc": now_iso(),
        })
        return {"block": block, "transactions": [decision_tx, refund_tx], "contract": contract, "deposit": deposit, "dispute": dispute, "damageReport": report, "mirror": mine_result["mirror"]}

    def admin_confirm_damage(self, dispute_id: str, req: AdminConfirmDamageRequest) -> dict:
        dispute, contract, deposit, report = self._get_dispute_bundle(dispute_id)
        self._ensure_dispute_status(dispute, ["choAdminXacMinh"], "xac nhan co hu hai")
        self._ensure_admin_user_context(req.adminid)
        admin_wallet = self._require_user_wallet(req.adminid, "admin")
        locked = self._locked_deposit_amount(deposit)
        if locked <= 0:
            raise ValueError("Deposit khong con so tien dang khoa de xu ly")
        if req.approvedcost > locked:
            raise ValueError("approvedCost vuot qua tien coc dang khoa")

        refund = locked - req.approvedcost
        payload = {
            "tranhChapId": dispute_id,
            "hopDongThueId": contract["id"],
            "adminId": req.adminid,
            "approvedCost": req.approvedcost,
            "decisionNote": req.decisionnote,
            "evidenceMeta": req.evidencemeta,
            "decision": "coHuHai",
        }
        decision_hash = self._build_evidence_hash("adminDecisionDamageConfirmed", payload)
        txs = [
            self.node.make_tx(
                "ADMIN_DECISION_DAMAGE_CONFIRMED",
                admin_wallet["address"],
                SYSTEM_ESCROW_ADDRESS,
                0,
                {
                    "hopDongThueId": contract["id"],
                    "tienCocId": deposit["id"],
                    "tranhChapId": dispute_id,
                    "baoCaoHuHaiId": report["id"] if report else None,
                    "decision": "coHuHai",
                    "decisionHash": decision_hash,
                    **payload,
                },
            )
        ]
        owner_tx = self.node.make_tx(
            "PAYOUT_DEPOSIT_TO_OWNER",
            SYSTEM_ESCROW_ADDRESS,
            contract["addresschuxe"],
            req.approvedcost,
            {
                "hopDongThueId": contract["id"],
                "tienCocId": deposit["id"],
                "tranhChapId": dispute_id,
                "action": "chuyenCocChoOwner",
                "decision": "coHuHai",
                "decisionHash": decision_hash,
                "approvedCost": req.approvedcost,
            },
        )
        txs.append(owner_tx)
        refund_tx = None
        if refund > 0:
            refund_tx = self.node.make_tx(
                "REFUND_DEPOSIT",
                SYSTEM_ESCROW_ADDRESS,
                contract["addressnguoithue"],
                refund,
                {
                    "hopDongThueId": contract["id"],
                    "tienCocId": deposit["id"],
                    "tranhChapId": dispute_id,
                    "action": "hoanPhanDuTienCoc",
                    "decision": "coHuHai",
                    "decisionHash": decision_hash,
                    "refundAmount": refund,
                },
            )
            txs.append(refund_tx)
        mine_result = self._mine_and_mirror(txs)
        block = mine_result["block"]
        dispute = self.update("disputes", "id", dispute_id, {
            "trangthai": self._db_status(DISPUTE_STATUS_DB, "daDong"),
            "ketquaxuly": "coHuHai",
            "sotienphaithu": req.approvedcost,
            "noidungketluan": req.decisionnote,
            "txhashresolve": txs[0]["txHash"],
            "capnhatluc": now_iso(),
        })
        if report:
            report = self.update("damage_reports", "id", report["id"], {
                "chiphisua": req.approvedcost,
                "trangthai": "daDong",
                "capnhatluc": now_iso(),
            })
        deposit = self.update("deposits", "id", deposit["id"], {
            "sotienhoancoc": refund,
            "sotienkhoacoc": 0,
            "txhashrefund": refund_tx["txHash"] if refund_tx else None,
            "hethongxuly": True,
            "trangthai": self._db_status(DEPOSIT_STATUS_DB, "daChuyenChoOwner" if refund == 0 else "daTatToan"),
            "capnhatluc": now_iso(),
        })
        contract = self.update("contracts", "id", contract["id"], {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "hoanThanh"),
            "txhashsettlement": owner_tx["txHash"],
            "blocknumbersettlement": block["blockHeight"],
            "tongtienhoanlai": refund,
            "danhanlaixe": True,
            "summaryhash": decision_hash,
            "capnhatluc": now_iso(),
        })
        return {"block": block, "transactions": txs, "contract": contract, "deposit": deposit, "dispute": dispute, "damageReport": report, "mirror": mine_result["mirror"]}
    def settle_contract(self, contract_id: str, tong_tien_thanh_toan: float, tong_tien_hoan_lai: float) -> dict:
        contract, deposit = self._get_contract_and_deposit(contract_id)
        if self._has_open_dispute(contract_id):
            raise ValueError("Contract dang tranh chap, khong the tat toan truc tiep")
        self._ensure_contract_status(contract, ["dangThue", "choKiemTraTraXe"], "tat toan")

        txs = [
            self.node.make_tx(
                "SETTLE_PAYMENT",
                contract["addressnguoithue"],
                contract["addresschuxe"],
                tong_tien_thanh_toan,
                {"hopDongThueId": contract_id, "tienCocId": deposit["id"], "action": "tatToan"},
            )
        ]
        refund_tx = None
        if tong_tien_hoan_lai > 0:
            refund_tx = self.node.make_tx(
                "REFUND_DEPOSIT",
                SYSTEM_ESCROW_ADDRESS,
                contract["addressnguoithue"],
                tong_tien_hoan_lai,
                {"hopDongThueId": contract_id, "tienCocId": deposit["id"], "action": "hoanCoc"},
            )
            txs.append(refund_tx)
        mine_result = self._mine_and_mirror(txs)
        block = mine_result["block"]
        contract = self.update("contracts", "id", contract_id, {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "hoanThanh"),
            "tongtienthanhtoan": tong_tien_thanh_toan,
            "tongtienhoanlai": tong_tien_hoan_lai,
            "txhashsettlement": txs[0]["txHash"],
            "blocknumbersettlement": block["blockHeight"],
            "danhanlaixe": True,
            "capnhatluc": now_iso(),
        })
        deposit = self.update("deposits", "id", deposit["id"], {
            "sotienhoancoc": tong_tien_hoan_lai,
            "sotienkhoacoc": 0,
            "txhashrefund": refund_tx["txHash"] if refund_tx else None,
            "hethongxuly": True,
            "trangthai": self._db_status(DEPOSIT_STATUS_DB, "daHoan" if tong_tien_hoan_lai > 0 else "daTatToan"),
            "capnhatluc": now_iso(),
        })
        return {"block": block, "transactions": txs, "hopDongThue": contract, "tienCoc": deposit, "mirror": mine_result["mirror"]}

    def overview(self) -> dict:
        chain = self.node.export_chain()
        blocks = chain.get("blocks", [])
        local_meta = chain.get("meta", {})
        db_latest = self._get_db_latest_block_meta()
        local_height = local_meta.get("latestBlockHeight")
        local_hash = local_meta.get("latestBlockHash")
        db_height = db_latest.get("blockheight")
        db_hash = db_latest.get("hash")
        sync_status = "synced" if local_height == db_height and local_hash == db_hash else "outOfSync"
        return {
            "users": self.list_rows("users", 20),
            "wallets": self.list_rows("wallets", 20),
            "vehicles": self.list_rows("vehicles", 20),
            "bookings": self.list_rows("bookings", 20),
            "contracts": self.list_rows("contracts", 20),
            "deposits": self.list_rows("deposits", 20),
            "damageReports": self.list_rows("damage_reports", 20),
            "disputes": self.list_rows("disputes", 20),
            "transactions": self.list_rows("transactions", 20),
            "events": self.list_rows("events", 20),
            "localLatestBlockHeight": local_height,
            "localLatestBlockHash": local_hash,
            "dbLatestBlockHeight": db_height,
            "dbLatestBlockHash": db_hash,
            "syncStatus": sync_status,
            "nodeChainMeta": local_meta,
            "latestBlock": blocks[-1] if blocks else None,
            "chain": chain,
        }
