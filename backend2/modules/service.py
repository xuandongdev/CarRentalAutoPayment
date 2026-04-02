import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from supabase import Client

from .config import (
    CONTRACT_STATUS_ALIASES,
    CONTRACT_STATUS_DB,
    DEPOSIT_STATUS_ALIASES,
    DEPOSIT_STATUS_DB,
    DISPUTE_STATUS_ALIASES,
    DISPUTE_STATUS_DB,
    PLATFORM_FEE_ADDRESS,
    PLATFORM_FEE_RATE,
    SYSTEM_ESCROW_ADDRESS,
    TABLES,
    TX_EVENT_NAMES,
)
from .models import (
    AddVehicleRequest,
    AdminConfirmDamageRequest,
    AdminConfirmNoDamageRequest,
    ConfirmContractStepRequest,
    CreateBookingRequest,
    CreateContractRequest,
    CreateDamageClaimRequest,
    ReturnVehicleRequest,
)
from .node_storage import LocalNodeStorage
from .utils import now_iso, sha256_obj, sha256_text


MONEY_QUANT = Decimal("0.00000001")
ZERO = Decimal("0")


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

    def safe_list_rows(self, table_key: str, limit: int = 10) -> tuple[list[dict], Optional[str]]:
        try:
            return self.list_rows(table_key, limit), None
        except Exception as exc:
            return [], str(exc)

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

    def _log_service_event(self, action: str, **fields):
        details = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
        print(f"[SERVICE] {now_iso()} action={action} {details}".strip())

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

    def _locked_deposit_amount(self, deposit: dict) -> Decimal:
        amount = self._decimal(deposit.get("sotienkhoacoc"))
        return amount if amount > ZERO else self._decimal(deposit.get("tonghoacoc"))

    def _deposit_status_in(self, deposit: Optional[dict], allowed_statuses: list[str]) -> bool:
        if deposit is None:
            return False
        return deposit.get("trangthai") in self._allowed_statuses(DEPOSIT_STATUS_ALIASES, allowed_statuses)

    def _logical_contract_status(self, contract: dict, deposit: Optional[dict]) -> str:
        raw_status = str(contract.get("trangthai") or "")
        if raw_status == self._db_status(CONTRACT_STATUS_DB, "hoanThanh"):
            return "hoanThanh"

        delivered = bool(contract.get("dagiaoxe"))
        owner_received = bool(contract.get("danhanlaixe"))

        if raw_status == self._db_status(CONTRACT_STATUS_DB, "khoiTao"):
            if delivered:
                return "choKhachNhanXe"
            if self._deposit_status_in(deposit, ["daKhoa", "tamGiuDoTranhChap", "daTatToan", "daHoan", "daChuyenChoOwner"]):
                return "choChuXacNhanGiaoXe"
            return "khoiTao"

        if raw_status == self._db_status(CONTRACT_STATUS_DB, "dangThue"):
            if self._deposit_status_in(deposit, ["tamGiuDoTranhChap"]):
                return "dangTranhChap"
            if owner_received:
                return "choTatToan"
            if delivered:
                return "dangThue"
            return "choChuXacNhanTraXe"

        return raw_status

    def _with_contract_flow_state(self, contract: dict, deposit: Optional[dict]) -> dict:
        logical_status = self._logical_contract_status(contract, deposit)
        item = dict(contract)
        item["trangthairaw"] = contract.get("trangthai")
        item["trangthailogical"] = logical_status
        item["trangthaihienthi"] = logical_status
        return item

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

    def _normalize_address(self, address: Optional[str]) -> Optional[str]:
        if address is None:
            return None
        text = str(address).strip()
        # Keep configured system addresses stable because wallet.address is a FK target by exact text.
        if text.lower() == str(SYSTEM_ESCROW_ADDRESS).strip().lower():
            return str(SYSTEM_ESCROW_ADDRESS).strip()
        if text.lower() == str(PLATFORM_FEE_ADDRESS).strip().lower():
            return str(PLATFORM_FEE_ADDRESS).strip()
        return text.lower() if text.lower().startswith("0x") else text

    def _decimal(self, value: Any) -> Decimal:
        if isinstance(value, Decimal):
            number = value
        elif value in (None, ""):
            number = ZERO
        else:
            number = Decimal(str(value))
        return number.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

    def _to_number(self, value: Any) -> float:
        return float(self._decimal(value))

    def _get_wallet_by_address(self, address: str) -> Optional[dict]:
        normalized = self._normalize_address(address)
        wallet = self.maybe_one("wallets", address=normalized)
        if wallet is None and normalized != address:
            wallet = self.maybe_one("wallets", address=address)
        return wallet

    def _require_wallet_by_address(self, address: str) -> dict:
        wallet = self._get_wallet_by_address(address)
        if wallet is None:
            raise ValueError(f"Khong tim thay vi voi address {address}")
        return wallet

    def _ensure_system_wallets(self) -> dict[str, dict]:
        wallets = {}
        for address in [SYSTEM_ESCROW_ADDRESS, PLATFORM_FEE_ADDRESS]:
            canonical = self._normalize_address(address)
            wallet = self._get_wallet_by_address(address)
            if wallet is None:
                wallet = self.insert("wallets", {
                    "nguoidungid": None,
                    "address": canonical,
                    "wallettype": "system",
                    "status": "active",
                    "balance": 0,
                    "lockedbalance": 0,
                    "syncat": now_iso(),
                    "createdat": now_iso(),
                })
            elif wallet.get("address") != canonical:
                wallet = self.update("wallets", "id", wallet["id"], {
                    "address": canonical,
                    "wallettype": "system",
                    "status": "active",
                    "syncat": now_iso(),
                })
            wallets[address] = wallet
        return wallets

    def _ensure_sufficient_balance(self, address: str, required_amount: Any):
        required = self._decimal(required_amount)
        wallet = self._require_wallet_by_address(address)
        balance = self._decimal(wallet.get("balance"))
        if balance < required:
            raise ValueError(f"Vi {wallet.get('address')} khong du balance, can {required} nhung chi co {balance}")

    def _ensure_sufficient_locked_balance(self, address: str, required_amount: Any):
        required = self._decimal(required_amount)
        wallet = self._require_wallet_by_address(address)
        locked = self._decimal(wallet.get("lockedbalance"))
        if locked < required:
            raise ValueError(f"Vi {wallet.get('address')} khong du lockedBalance, can {required} nhung chi co {locked}")

    def _update_wallet_balance(self, address: str, delta_balance: Any, delta_locked_balance: Any = ZERO) -> dict:
        wallet = self._require_wallet_by_address(address)
        new_balance = self._decimal(wallet.get("balance")) + self._decimal(delta_balance)
        new_locked = self._decimal(wallet.get("lockedbalance")) + self._decimal(delta_locked_balance)
        if new_balance < ZERO:
            raise ValueError(f"Khong the cap nhat wallet {address} vi balance se am")
        if new_locked < ZERO:
            raise ValueError(f"Khong the cap nhat wallet {address} vi lockedBalance se am")
        return self.update("wallets", "id", wallet["id"], {
            "balance": self._to_number(new_balance),
            "lockedbalance": self._to_number(new_locked),
            "syncat": now_iso(),
        })

    def _calculate_platform_fee(self, amount: Any) -> Decimal:
        return (self._decimal(amount) * Decimal(str(PLATFORM_FEE_RATE))).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

    def _split_amount_with_fee(self, amount: Any) -> dict[str, Decimal]:
        gross_amount = self._decimal(amount)
        fee_amount = self._calculate_platform_fee(gross_amount)
        net_amount = (gross_amount - fee_amount).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
        if net_amount < ZERO:
            raise ValueError("Net amount khong hop le sau khi tru phi")
        return {
            "gross_amount": gross_amount,
            "fee_amount": fee_amount,
            "net_amount": net_amount,
        }

    def _money_flow_raw(self, *, contract_id: str, deposit_id: Optional[str], dispute_id: Optional[str], business_action: str, gross: Any = ZERO, fee: Any = ZERO, net: Any = ZERO, extra: Optional[dict] = None) -> dict:
        payload = {
            "hopDongThueId": contract_id,
            "tienCocId": deposit_id,
            "tranhChapId": dispute_id,
            "businessAction": business_action,
            "grossAmount": self._to_number(gross),
            "feeAmount": self._to_number(fee),
            "netAmount": self._to_number(net),
            "feeRate": PLATFORM_FEE_RATE,
            "balancesSeededManually": True,
            "note": "Deposit/withdraw real payment gateway not implemented; balances are seeded manually for blockchain flow testing.",
        }
        if extra:
            payload.update(extra)
        return payload

    def _make_tx(self, tx_type: str, from_address: Optional[str], to_address: Optional[str], amount: Any, raw_data: dict) -> dict:
        return self.node.make_tx(
            tx_type,
            self._normalize_address(from_address),
            self._normalize_address(to_address),
            self._to_number(amount),
            raw_data,
        )

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
            str(raw.get("businessAction") or ""),
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
                "businessAction": tx["rawData"].get("businessAction"),
                "grossAmount": tx["rawData"].get("grossAmount"),
                "feeAmount": tx["rawData"].get("feeAmount"),
                "netAmount": tx["rawData"].get("netAmount"),
                "feeRate": tx["rawData"].get("feeRate"),
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
        self._align_local_head_with_db()
        block = self.node.mine_block(txs)
        mirror_stats = self.mirror_block(block)
        return {"block": block, "mirror": mirror_stats}

    def _get_db_latest_block_meta(self) -> dict:
        result = self.t("blocks").select("blockheight,hash").order("blockheight", desc=True).limit(1).execute()
        if not result.data:
            return {"blockheight": None, "hash": None}
        return result.data[0]

    def _safe_db_latest_block_meta(self) -> tuple[dict, Optional[str]]:
        try:
            return self._get_db_latest_block_meta(), None
        except Exception as exc:
            return {"blockheight": None, "hash": None}, str(exc)

    def _align_local_head_with_db(self):
        db_latest = self._get_db_latest_block_meta()
        db_height = db_latest.get("blockheight")
        db_hash = db_latest.get("hash")
        if db_height is None or not db_hash:
            return
        local_meta = self.node.get_meta()
        local_height = int(local_meta.get("latestBlockHeight", 0))
        local_hash = local_meta.get("latestBlockHash")
        if db_height > local_height or (db_height == local_height and db_hash != local_hash):
            self.node.sync_head(int(db_height), db_hash)

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

    def _vehicle_activity_maps(self, vehicle_ids: list[str]) -> tuple[dict[str, int], dict[str, int]]:
        if not vehicle_ids:
            return {}, {}
        pending_map: dict[str, int] = {}
        renting_map: dict[str, int] = {}

        booking_rows = (
            self.t("bookings")
            .select("xeid,trangthai")
            .in_("xeid", vehicle_ids)
            .in_("trangthai", ["choXacNhan", "daDuyet", "daTaoHopDong"])
            .limit(5000)
            .execute()
            .data
            or []
        )
        for row in booking_rows:
            xe_id = row.get("xeid")
            if xe_id:
                pending_map[xe_id] = pending_map.get(xe_id, 0) + 1

        contract_rows = (
            self.t("contracts")
            .select("xeid,trangthai")
            .in_("xeid", vehicle_ids)
            .in_("trangthai", ["khoiTao", "dangThue"])
            .limit(5000)
            .execute()
            .data
            or []
        )
        for row in contract_rows:
            xe_id = row.get("xeid")
            if not xe_id:
                continue
            if row.get("trangthai") == "dangThue":
                renting_map[xe_id] = renting_map.get(xe_id, 0) + 1
            else:
                pending_map[xe_id] = pending_map.get(xe_id, 0) + 1
        return pending_map, renting_map

    def _decorate_vehicle_row(self, vehicle: dict, pending_count: int, renting_count: int) -> dict:
        status = vehicle.get("trangthai")
        display_code = status
        display_label = status
        can_book = False

        if status == "choDuyet":
            display_code, display_label = "choDuyet", "Chờ duyệt"
        elif status == "baoTri":
            display_code, display_label = "baoTri", "Bảo trì"
        elif status == "ngungHoatDong":
            display_code, display_label = "ngungHoatDong", "Ngừng hoạt động"
        elif status == "dangThue" or renting_count > 0:
            display_code, display_label = "dangChoThue", "Đang cho thuê"
        elif status == "sanSang" and pending_count > 0:
            display_code, display_label = "dangCho", "Đang chờ"
        elif status == "sanSang":
            display_code, display_label = "sanSang", "Sẵn sàng"
            can_book = True
        else:
            display_code, display_label = str(status or "unknown"), str(status or "unknown")

        return {
            **vehicle,
            "displaytrangthai": display_code,
            "displaytrangthailabel": display_label,
            "canbook": can_book,
        }

    def _decorate_vehicle_rows(self, rows: list[dict]) -> list[dict]:
        vehicle_ids = [row.get("id") for row in rows if row.get("id")]
        pending_map, renting_map = self._vehicle_activity_maps(vehicle_ids)
        return [
            self._decorate_vehicle_row(
                row,
                pending_count=pending_map.get(row.get("id"), 0),
                renting_count=renting_map.get(row.get("id"), 0),
            )
            for row in rows
        ]

    def _vehicle_is_bookable(self, vehicle_id: str) -> bool:
        pending_map, renting_map = self._vehicle_activity_maps([vehicle_id])
        return pending_map.get(vehicle_id, 0) == 0 and renting_map.get(vehicle_id, 0) == 0

    def _refresh_vehicle_status_by_activity(self, vehicle_id: str):
        vehicle = self.one("vehicles", id=vehicle_id)
        current = vehicle.get("trangthai")
        if current in {"choDuyet", "baoTri", "ngungHoatDong"}:
            return
        _, renting_map = self._vehicle_activity_maps([vehicle_id])
        target = "dangThue" if renting_map.get(vehicle_id, 0) > 0 else "sanSang"
        if current != target:
            self.update("vehicles", "id", vehicle_id, {"trangthai": target, "capnhatluc": now_iso()})

    def _complete_booking_for_contract(self, contract: dict):
        booking_id = contract.get("dangkyid")
        if not booking_id:
            return
        booking = self.maybe_one("bookings", id=booking_id)
        if booking is None:
            return
        current_status = booking.get("trangthai")
        if current_status not in {"choXacNhan", "daDuyet", "daTaoHopDong"}:
            return
        self.update("bookings", "id", booking_id, {
            "trangthai": "hoanTat",
            "capnhatluc": now_iso(),
        })

    def _active_user_wallet(self, user_id: str) -> Optional[dict]:
        wallets = self.t("wallets").select("*").eq("nguoidungid", user_id).limit(20).execute().data or []
        if not wallets:
            return None
        for wallet in wallets:
            if wallet.get("status") == "active":
                return wallet
        return wallets[0]

    def _default_deposit_amount(self, tong_tien_thue: Any) -> float:
        return self._to_number(self._decimal(tong_tien_thue) * Decimal("0.30"))

    def _create_contract_and_deposit_for_booking(self, booking: dict, tong_tien_coc: float) -> dict:
        existed = self.maybe_one("contracts", dangkyid=booking["id"])
        if existed:
            raise ValueError("Dang ky nay da co hop dong")
        vehicle = self.one("vehicles", id=booking["xeid"])
        renter = self.one("users", id=booking["nguoidungid"])
        owner = self.one("users", id=vehicle["chuxeid"])
        renter_wallet = self._active_user_wallet(renter["id"])
        owner_wallet = self._active_user_wallet(owner["id"])
        contract_hash = sha256_obj({
            "bookingId": booking["id"],
            "xeId": vehicle["id"],
            "nguoiThueId": renter["id"],
            "chuXeId": owner["id"],
            "tongTienCoc": tong_tien_coc,
            "createdAt": now_iso(),
        })
        contract = self.insert("contracts", {
            "dangkyid": booking["id"],
            "xeid": vehicle["id"],
            "nguoithueid": renter["id"],
            "chuxeid": owner["id"],
            "addressnguoithue": None if renter_wallet is None else renter_wallet.get("address"),
            "addresschuxe": None if owner_wallet is None else owner_wallet.get("address"),
            "contracthash": contract_hash,
            "signaturenguoithue": sha256_text("sign|renter|" + contract_hash),
            "signaturechuxe": sha256_text("sign|owner|" + contract_hash),
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "khoiTao"),
            "tongtiencoc": tong_tien_coc,
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
            "tonghoacoc": tong_tien_coc,
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
        booking = self.update("bookings", "id", booking["id"], {"trangthai": "daTaoHopDong", "capnhatluc": now_iso()})
        return {"booking": booking, "hopDongThue": contract, "tienCoc": deposit}

    def _create_booking_contract_via_rpc(self, renter_id: str, req: CreateBookingRequest, so_ngay: int, tong_tien_thue: float, tong_tien_coc: float) -> Optional[dict]:
        params = {
            "p_nguoidungid": renter_id,
            "p_xeid": req.xeid,
            "p_songaythue": so_ngay,
            "p_diadiemnhan": req.diadiemnhan,
            "p_tongtienthue": tong_tien_thue,
            "p_ghichu": req.ghichu or "Tao tu giao dien nguoi dung",
            "p_tongtiencoc": tong_tien_coc,
        }
        result = self.supabase.rpc("create_booking_with_contract_atomic", params).execute()
        data = result.data
        if not data:
            return None
        payload = data[0] if isinstance(data, list) else data
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            return None
        booking = payload.get("booking")
        contract = payload.get("hopDongThue")
        deposit = payload.get("tienCoc")
        if booking and contract and deposit:
            return {"booking": booking, "hopDongThue": contract, "tienCoc": deposit}
        return None

    def list_public_vehicles(self) -> list[dict]:
        rows = self.t("vehicles").select("*").in_("trangthai", ["sanSang", "choDuyet"]).order("taoluc", desc=True).limit(300).execute().data or []
        return self._decorate_vehicle_rows(rows)

    def list_owner_vehicles(self, owner_id: str) -> list[dict]:
        rows = self.t("vehicles").select("*").eq("chuxeid", owner_id).order("taoluc", desc=True).limit(300).execute().data or []
        return self._decorate_vehicle_rows(rows)

    def list_admin_vehicles(self) -> list[dict]:
        rows = self.t("vehicles").select("*").order("taoluc", desc=True).limit(500).execute().data or []
        return self._decorate_vehicle_rows(rows)

    def list_owner_availability(self, owner_id: str) -> list[dict]:
        vehicle_rows = self.list_owner_vehicles(owner_id)
        vehicle_ids = [row.get("id") for row in vehicle_rows if row.get("id")]
        if not vehicle_ids:
            return []
        return self.t("schedules").select("*").in_("xeid", vehicle_ids).order("ngaybatdau", desc=True).limit(500).execute().data or []

    def list_renter_bookings(self, renter_id: str) -> list[dict]:
        return self.t("bookings").select("*").eq("nguoidungid", renter_id).order("taoluc", desc=True).limit(300).execute().data or []

    def list_contracts_for_user(self, user_id: str) -> list[dict]:
        rows = self.t("contracts").select("*").order("taoluc", desc=True).limit(500).execute().data or []
        filtered = [row for row in rows if row.get("nguoithueid") == user_id or row.get("chuxeid") == user_id]
        contract_ids = [row.get("id") for row in filtered if row.get("id")]
        deposits = (
            self.t("deposits")
            .select("*")
            .in_("hopdongthueid", contract_ids)
            .limit(max(len(contract_ids), 1) * 2)
            .execute()
            .data
            or []
        ) if contract_ids else []
        deposit_map = {row.get("hopdongthueid"): row for row in deposits if row.get("hopdongthueid")}
        return [self._with_contract_flow_state(row, deposit_map.get(row.get("id"))) for row in filtered]

    def list_disputes_for_owner(self, owner_id: str) -> list[dict]:
        contract_rows = self.t("contracts").select("id,chuxeid").eq("chuxeid", owner_id).limit(500).execute().data or []
        contract_ids = [row.get("id") for row in contract_rows if row.get("id")]
        if not contract_ids:
            return []
        return self.t("disputes").select("*").in_("hopdongthueid", contract_ids).order("taoluc", desc=True).limit(500).execute().data or []

    def list_deposits_for_renter(self, renter_id: str) -> list[dict]:
        contract_rows = self.t("contracts").select("id,nguoithueid").eq("nguoithueid", renter_id).limit(500).execute().data or []
        contract_ids = [row.get("id") for row in contract_rows if row.get("id")]
        if not contract_ids:
            return []
        return self.t("deposits").select("*").in_("hopdongthueid", contract_ids).order("taoluc", desc=True).limit(500).execute().data or []

    def add_availability(self, owner_id: str, xe_id: str, ngay_bat_dau: str, ngay_ket_thuc: str, con_trong: bool, ghi_chu: Optional[str]) -> dict:
        vehicle = self.one("vehicles", id=xe_id)
        if vehicle.get("chuxeid") != owner_id:
            raise ValueError("Ban chi duoc tao lich trong cho xe cua chinh minh")
        return self.insert("schedules", {
            "xeid": xe_id,
            "controng": con_trong,
            "ghichu": ghi_chu,
            "ngaybatdau": ngay_bat_dau,
            "ngayketthuc": ngay_ket_thuc,
            "taoluc": now_iso(),
        })

    def update_vehicle_status(self, vehicle_id: str, status: str) -> dict:
        self.one("vehicles", id=vehicle_id)
        return self.update("vehicles", "id", vehicle_id, {"trangthai": status, "capnhatluc": now_iso()})

    def add_vehicle(self, owner_id: str, req: AddVehicleRequest) -> dict:
        self._log_service_event("add_vehicle_attempt", ownerId=owner_id, bienSo=req.bienso)
        existed = self.maybe_one("vehicles", bienso=req.bienso)
        if existed:
            raise ValueError("Bien so da ton tai")
        vehicle = self.insert("vehicles", {
            "chuxeid": owner_id,
            "bienso": req.bienso,
            "namsanxuat": req.namsanxuat,
            "mota": req.mota or f"{req.hangxe} {req.dongxe}",
            "hangxe": req.hangxe,
            "dongxe": req.dongxe,
            "loaixe": req.loaixe,
            "trangthai": "choDuyet",
            "giatheongay": req.giatheongay,
            "giatheogio": req.giatheogio,
            "baohiem": req.baohiem,
            "dangkiem": req.dangkiem,
            "dangkyxe": req.dangkyxe,
            "ngayhethandangkiem": req.ngayhethandangkiem,
            "taoluc": now_iso(),
            "capnhatluc": now_iso(),
        })
        self._log_service_event("add_vehicle_success", vehicleId=vehicle.get("id"), bienSo=vehicle.get("bienso"), ownerId=vehicle.get("chuxeid"))
        return vehicle

    def create_booking(self, renter_id: str, req: CreateBookingRequest) -> dict:
        self._log_service_event("create_booking_attempt", renterId=renter_id, xeId=req.xeid)
        renter = self.one("users", id=renter_id)
        if renter.get("vaitro") != "khach":
            raise ValueError("Chi nguoi dung vai tro khach moi duoc dat xe")
        if renter.get("trangthai") != "hoatDong":
            raise ValueError("Tai khoan khong o trang thai hoat dong")
        vehicle = self.one("vehicles", id=req.xeid)
        if vehicle.get("trangthai") != "sanSang":
            raise ValueError("Xe khong o trang thai san sang de dat")
        if not self._vehicle_is_bookable(vehicle["id"]):
            raise ValueError("Xe dang cho xu ly booking/hop dong khac, vui long chon xe khac")
        duplicate_booking = (
            self.t("bookings")
            .select("id")
            .eq("nguoidungid", renter_id)
            .eq("xeid", vehicle["id"])
            .in_("trangthai", ["choXacNhan", "daDuyet", "daTaoHopDong"])
            .limit(1)
            .execute()
            .data
            or []
        )
        if duplicate_booking:
            raise ValueError("Ban da co booking dang xu ly cho xe nay")
        so_ngay = req.songaythue or 1
        if req.ngaybatdau and req.ngayketthuc:
            from datetime import datetime
            start = datetime.fromisoformat(req.ngaybatdau.replace("Z", "+00:00"))
            end = datetime.fromisoformat(req.ngayketthuc.replace("Z", "+00:00"))
            diff = (end - start).days
            so_ngay = diff if diff > 0 else 1
        tong_tien = self._to_number(self._decimal(vehicle.get("giatheongay")) * Decimal(str(so_ngay)))
        tong_tien_coc = self._default_deposit_amount(tong_tien)

        try:
            rpc_result = self._create_booking_contract_via_rpc(renter_id, req, so_ngay, tong_tien, tong_tien_coc)
            if rpc_result:
                self._log_service_event("create_booking_success_atomic_rpc", bookingId=rpc_result["booking"].get("id"), renterId=renter_id, xeId=vehicle.get("id"))
                return {**rpc_result, "note": "Dat xe thanh cong, hop dong da duoc tao tu dong"}
        except Exception as exc:
            self._log_service_event("create_booking_rpc_fallback", reason=str(exc), renterId=renter_id, xeId=req.xeid)

        booking = None
        contract = None
        deposit = None
        try:
            booking = self.insert("bookings", {
                "nguoidungid": renter_id,
                "xeid": vehicle["id"],
                "songaythue": so_ngay,
                "diadiemnhan": req.diadiemnhan,
                "tongtienthue": tong_tien,
                "trangthai": "choXacNhan",
                "ghichu": req.ghichu or "Tao tu giao dien nguoi dung",
                "taoluc": now_iso(),
                "capnhatluc": now_iso(),
            })
            created = self._create_contract_and_deposit_for_booking(booking, tong_tien_coc)
            contract = created["hopDongThue"]
            deposit = created["tienCoc"]
            booking = created["booking"]
        except Exception:
            if deposit and deposit.get("id"):
                self.t("deposits").delete().eq("id", deposit["id"]).execute()
            if contract and contract.get("id"):
                self.t("contracts").delete().eq("id", contract["id"]).execute()
            if booking and booking.get("id"):
                self.t("bookings").delete().eq("id", booking["id"]).execute()
            raise

        self._log_service_event("create_booking_success", bookingId=booking.get("id"), renterId=booking.get("nguoidungid"), xeId=booking.get("xeid"), contractId=contract.get("id"))
        return {"booking": booking, "hopDongThue": contract, "tienCoc": deposit, "note": "Dat xe thanh cong, hop dong da duoc tao tu dong"}

    def create_contract_from_booking(self, req: CreateContractRequest) -> dict:
        self._log_service_event("create_contract_attempt", dangKyId=req.dangkyid, tongTienCoc=req.tongtiencoc)
        booking = self.one("bookings", id=req.dangkyid)
        created = self._create_contract_and_deposit_for_booking(booking, req.tongtiencoc)
        self._log_service_event("create_contract_success", contractId=created["hopDongThue"].get("id"), bookingId=booking.get("id"))
        return {"hopDongThue": created["hopDongThue"], "tienCoc": created["tienCoc"], "booking": created["booking"]}

    def lock_deposit(self, contract_id: str) -> dict:
        self._log_service_event("lock_deposit_attempt", contractId=contract_id)
        self._ensure_system_wallets()
        contract, deposit = self._get_contract_and_deposit(contract_id)
        self._ensure_contract_status(contract, ["khoiTao", "choKhoaCoc"], "khoa coc")
        if deposit.get("trangthai") not in self._allowed_statuses(DEPOSIT_STATUS_ALIASES, ["chuaKhoa"]):
            raise ValueError("Tien coc da duoc xu ly, khong the khoa lai")

        amount = self._decimal(deposit["tonghoacoc"])
        renter_address = contract["addressnguoithue"]
        escrow_address = SYSTEM_ESCROW_ADDRESS
        self._ensure_sufficient_balance(renter_address, amount)

        txs = [
            self._make_tx(
                "LOCK_DEPOSIT",
                renter_address,
                escrow_address,
                amount,
                self._money_flow_raw(
                    contract_id=contract_id,
                    deposit_id=deposit["id"],
                    dispute_id=None,
                    business_action="lockDeposit",
                    gross=amount,
                    net=amount,
                    extra={"action": "khoaCoc"},
                ),
            ),
            self._make_tx(
                "ESCROW_LOCK",
                renter_address,
                escrow_address,
                amount,
                self._money_flow_raw(
                    contract_id=contract_id,
                    deposit_id=deposit["id"],
                    dispute_id=None,
                    business_action="escrowLock",
                    gross=amount,
                    net=amount,
                ),
            ),
        ]
        mine_result = self._mine_and_mirror(txs)
        block = mine_result["block"]

        # Custody is moved into the escrow system wallet; renter.lockedBalance reflects funds still reserved for the contract.
        self._update_wallet_balance(renter_address, -amount, amount)
        self._update_wallet_balance(escrow_address, amount, ZERO)

        deposit = self.update("deposits", "id", deposit["id"], {
            "sotienkhoacoc": self._to_number(amount),
            "txhashlock": txs[0]["txHash"],
            "hethongxuly": True,
            "trangthai": self._db_status(DEPOSIT_STATUS_DB, "daKhoa"),
            "capnhatluc": now_iso(),
        })
        contract = self.update("contracts", "id", contract_id, {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "khoiTao"),
            "dagiaoxe": False,
            "danhanlaixe": False,
            "capnhatluc": now_iso(),
        })
        self._refresh_vehicle_status_by_activity(contract["xeid"])
        self._log_service_event("lock_deposit_success", contractId=contract_id, txHash=txs[0].get("txHash"), blockHeight=block.get("blockHeight"), amount=self._to_number(amount))
        return {"block": block, "transactions": txs, "transaction": txs[0], "hopDongThue": contract, "tienCoc": deposit, "mirror": mine_result["mirror"]}

    def owner_confirm_handover(self, contract_id: str, actor_user_id: str, req: ConfirmContractStepRequest) -> dict:
        self._log_service_event("owner_confirm_handover_attempt", contractId=contract_id, ownerId=actor_user_id)
        contract, deposit = self._get_contract_and_deposit(contract_id)
        if actor_user_id != contract["chuxeid"]:
            raise ValueError("Nguoi xac nhan giao xe khong dung voi chu xe cua contract")
        if contract.get("trangthai") == self._db_status(CONTRACT_STATUS_DB, "hoanThanh"):
            raise ValueError("Contract da hoan thanh, khong the xac nhan giao xe")
        if not self._deposit_status_in(deposit, ["daKhoa"]):
            raise ValueError("Can khoa coc truoc khi chu xe xac nhan giao xe")
        if bool(contract.get("dagiaoxe")):
            raise ValueError("Chu xe da xac nhan giao xe truoc do")

        payload = {
            "hopDongThueId": contract_id,
            "chuXeId": actor_user_id,
            "ghiChu": req.ghichu,
            "evidenceUrls": req.evidenceurls,
            "evidenceMeta": req.evidencemeta,
        }
        evidence_hash = self._build_evidence_hash("ownerHandoverConfirmed", payload)
        tx = self.node.make_tx(
            "OWNER_HANDOVER_CONFIRMED",
            contract["addresschuxe"],
            contract["addressnguoithue"],
            0,
            {
                "hopDongThueId": contract_id,
                "tienCocId": deposit["id"],
                "action": "ownerConfirmHandover",
                "evidenceHash": evidence_hash,
                **payload,
            },
        )
        mine_result = self._mine_and_mirror([tx])
        block = mine_result["block"]

        contract = self.update("contracts", "id", contract_id, {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "khoiTao"),
            "dagiaoxe": True,
            "danhanlaixe": False,
            "summaryhash": evidence_hash,
            "capnhatluc": now_iso(),
        })
        self._log_service_event("owner_confirm_handover_success", contractId=contract_id, txHash=tx.get("txHash"), blockHeight=block.get("blockHeight"))
        return {"block": block, "transaction": tx, "contract": contract, "mirror": mine_result["mirror"], "handoverEvidenceHash": evidence_hash}

    def renter_confirm_receive(self, contract_id: str, actor_user_id: str, req: ConfirmContractStepRequest) -> dict:
        self._log_service_event("renter_confirm_receive_attempt", contractId=contract_id, renterId=actor_user_id)
        contract, deposit = self._get_contract_and_deposit(contract_id)
        if actor_user_id != contract["nguoithueid"]:
            raise ValueError("Nguoi xac nhan nhan xe khong dung voi nguoi thue cua contract")
        if contract.get("trangthai") == self._db_status(CONTRACT_STATUS_DB, "hoanThanh"):
            raise ValueError("Contract da hoan thanh, khong the xac nhan nhan xe")
        if not self._deposit_status_in(deposit, ["daKhoa"]):
            raise ValueError("Can khoa coc truoc khi xac nhan nhan xe")
        if not bool(contract.get("dagiaoxe")):
            raise ValueError("Chu xe chua xac nhan giao xe")
        if contract.get("trangthai") == self._db_status(CONTRACT_STATUS_DB, "dangThue"):
            raise ValueError("Hop dong da o trang thai dang thue, khong the xac nhan nhan xe lap lai")

        payload = {
            "hopDongThueId": contract_id,
            "nguoiThueId": actor_user_id,
            "ghiChu": req.ghichu,
            "evidenceUrls": req.evidenceurls,
            "evidenceMeta": req.evidencemeta,
        }
        evidence_hash = self._build_evidence_hash("renterReceiveConfirmed", payload)
        tx = self.node.make_tx(
            "RENTER_RECEIVE_CONFIRMED",
            contract["addressnguoithue"],
            contract["addresschuxe"],
            0,
            {
                "hopDongThueId": contract_id,
                "tienCocId": deposit["id"],
                "action": "renterConfirmReceive",
                "evidenceHash": evidence_hash,
                **payload,
            },
        )
        mine_result = self._mine_and_mirror([tx])
        block = mine_result["block"]

        contract = self.update("contracts", "id", contract_id, {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "dangThue"),
            "summaryhash": evidence_hash,
            "capnhatluc": now_iso(),
        })
        self._refresh_vehicle_status_by_activity(contract["xeid"])
        self._log_service_event("renter_confirm_receive_success", contractId=contract_id, txHash=tx.get("txHash"), blockHeight=block.get("blockHeight"))
        return {"block": block, "transaction": tx, "contract": contract, "mirror": mine_result["mirror"], "receiveEvidenceHash": evidence_hash}

    def return_vehicle(self, contract_id: str, actor_user_id: str, req: ReturnVehicleRequest) -> dict:
        self._log_service_event("return_vehicle_attempt", contractId=contract_id, nguoiTraId=actor_user_id)
        contract, deposit = self._get_contract_and_deposit(contract_id)
        if contract.get("trangthai") != self._db_status(CONTRACT_STATUS_DB, "dangThue"):
            raise ValueError("Chi duoc tra xe khi hop dong dang o trang thai dang thue")
        if contract.get("danhanlaixe"):
            raise ValueError("Contract da o sau buoc tra xe, khong the tra xe lap lai")
        if not bool(contract.get("dagiaoxe")):
            raise ValueError("Hop dong khong o buoc dang su dung xe hoac da tra xe truoc do")
        if actor_user_id != contract["nguoithueid"]:
            raise ValueError("Nguoi tra xe khong dung voi nguoi thue cua contract")
        if not self._deposit_status_in(deposit, ["daKhoa"]):
            raise ValueError("Deposit chua khoa hoac khong con o trang thai cho phep tra xe")
        payload = {
            "hopDongThueId": contract_id,
            "nguoiTraId": actor_user_id,
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
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "dangThue"),
            "dagiaoxe": False,
            "danhanlaixe": False,
            "summaryhash": evidence_hash,
            "capnhatluc": now_iso(),
        })
        self._log_service_event("return_vehicle_success", contractId=contract_id, txHash=tx.get("txHash"), blockHeight=block.get("blockHeight"))
        return {"block": block, "transaction": tx, "contract": contract, "mirror": mine_result["mirror"], "returnEvidenceHash": evidence_hash}

    def owner_confirm_return(self, contract_id: str, actor_user_id: str, req: ConfirmContractStepRequest) -> dict:
        self._log_service_event("owner_confirm_return_attempt", contractId=contract_id, ownerId=actor_user_id)
        contract, deposit = self._get_contract_and_deposit(contract_id)
        if actor_user_id != contract["chuxeid"]:
            raise ValueError("Nguoi xac nhan nhan lai xe khong dung voi chu xe cua contract")
        if contract.get("trangthai") != self._db_status(CONTRACT_STATUS_DB, "dangThue"):
            raise ValueError("Chi duoc xac nhan nhan lai xe khi hop dong dang o trang thai dang thue")
        if bool(contract.get("danhanlaixe")):
            raise ValueError("Chu xe da xac nhan nhan lai xe truoc do")
        if bool(contract.get("dagiaoxe")):
            raise ValueError("Khach chua xac nhan tra xe")
        if not self._deposit_status_in(deposit, ["daKhoa", "tamGiuDoTranhChap"]):
            raise ValueError("Deposit khong o trang thai cho phep xac nhan tra xe")

        payload = {
            "hopDongThueId": contract_id,
            "chuXeId": actor_user_id,
            "ghiChu": req.ghichu,
            "evidenceUrls": req.evidenceurls,
            "evidenceMeta": req.evidencemeta,
        }
        evidence_hash = self._build_evidence_hash("ownerReturnConfirmed", payload)
        tx = self.node.make_tx(
            "OWNER_RETURN_CONFIRMED",
            contract["addresschuxe"],
            contract["addressnguoithue"],
            0,
            {
                "hopDongThueId": contract_id,
                "tienCocId": deposit["id"],
                "action": "ownerConfirmReturn",
                "evidenceHash": evidence_hash,
                **payload,
            },
        )
        mine_result = self._mine_and_mirror([tx])
        block = mine_result["block"]

        contract = self.update("contracts", "id", contract_id, {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "dangThue"),
            "danhanlaixe": True,
            "summaryhash": evidence_hash,
            "capnhatluc": now_iso(),
        })
        self._log_service_event("owner_confirm_return_success", contractId=contract_id, txHash=tx.get("txHash"), blockHeight=block.get("blockHeight"))
        return {"block": block, "transaction": tx, "contract": contract, "mirror": mine_result["mirror"], "ownerReturnEvidenceHash": evidence_hash}

    def create_damage_claim(self, contract_id: str, actor_owner_id: str, req: CreateDamageClaimRequest) -> dict:
        self._log_service_event("damage_claim_attempt", contractId=contract_id, ownerId=actor_owner_id, estimatedCost=req.estimatedcost)
        contract, deposit = self._get_contract_and_deposit(contract_id)
        self._ensure_contract_status(contract, ["dangThue", "choKiemTraTraXe"], "tao khieu nai hu hai")
        if not contract.get("danhanlaixe"):
            raise ValueError("Chi duoc khieu nai sau khi xe da duoc tra")
        if actor_owner_id != contract["chuxeid"]:
            raise ValueError("ownerId khong dung voi chu xe cua contract")
        if deposit.get("trangthai") not in self._allowed_statuses(DEPOSIT_STATUS_ALIASES, ["daKhoa", "tamGiuDoTranhChap"]):
            raise ValueError("Deposit chua khoa ma da tranh chap")
        if self._has_open_dispute(contract_id):
            raise ValueError("Contract nay da co tranh chap dang mo")

        payload = {
            "hopDongThueId": contract_id,
            "ownerId": actor_owner_id,
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
        self._log_service_event("damage_claim_success", contractId=contract_id, disputeId=dispute.get("id"), reportId=report.get("id"), txHash=tx.get("txHash"))
        return {"block": block, "transaction": tx, "contract": contract, "deposit": deposit, "dispute": dispute, "damageReport": report, "mirror": mine_result["mirror"]}

    def admin_confirm_no_damage(self, dispute_id: str, admin_id: str, req: AdminConfirmNoDamageRequest) -> dict:
        self._log_service_event("admin_confirm_no_damage_attempt", disputeId=dispute_id, adminId=admin_id)
        self._ensure_system_wallets()
        dispute, contract, deposit, report = self._get_dispute_bundle(dispute_id)
        self._ensure_dispute_status(dispute, ["choAdminXacMinh"], "xac nhan khong hu hai")
        self._ensure_admin_user_context(admin_id)
        admin_wallet = self._require_user_wallet(admin_id, "admin")
        locked = self._locked_deposit_amount(deposit)
        if locked <= ZERO:
            raise ValueError("Deposit khong con so tien dang khoa de hoan")

        escrow_address = SYSTEM_ESCROW_ADDRESS
        renter_address = contract["addressnguoithue"]
        self._ensure_sufficient_balance(escrow_address, locked)
        self._ensure_sufficient_locked_balance(renter_address, locked)

        payload = {
            "tranhChapId": dispute_id,
            "hopDongThueId": contract["id"],
            "adminId": admin_id,
            "decisionNote": req.decisionnote,
            "evidenceMeta": req.evidencemeta,
            "decision": "khongCoHuHai",
        }
        decision_hash = self._build_evidence_hash("adminDecisionNoDamage", payload)
        txs = [
            self._make_tx(
                "ADMIN_DECISION_NO_DAMAGE",
                admin_wallet["address"],
                escrow_address,
                ZERO,
                {
                    **self._money_flow_raw(
                        contract_id=contract["id"],
                        deposit_id=deposit["id"],
                        dispute_id=dispute_id,
                        business_action="adminDecisionNoDamage",
                    ),
                    "baoCaoHuHaiId": report["id"] if report else None,
                    "decision": "khongCoHuHai",
                    "decisionHash": decision_hash,
                    **payload,
                },
            ),
            self._make_tx(
                "REFUND_DEPOSIT",
                escrow_address,
                renter_address,
                locked,
                {
                    **self._money_flow_raw(
                        contract_id=contract["id"],
                        deposit_id=deposit["id"],
                        dispute_id=dispute_id,
                        business_action="refundDeposit",
                        gross=locked,
                        net=locked,
                    ),
                    "decision": "khongCoHuHai",
                    "decisionHash": decision_hash,
                },
            ),
            self._make_tx(
                "ESCROW_REFUND",
                escrow_address,
                renter_address,
                locked,
                self._money_flow_raw(
                    contract_id=contract["id"],
                    deposit_id=deposit["id"],
                    dispute_id=dispute_id,
                    business_action="escrowRefund",
                    gross=locked,
                    net=locked,
                ),
            ),
        ]
        mine_result = self._mine_and_mirror(txs)
        block = mine_result["block"]

        self._update_wallet_balance(escrow_address, -locked, ZERO)
        self._update_wallet_balance(renter_address, locked, -locked)

        dispute = self.update("disputes", "id", dispute_id, {
            "trangthai": self._db_status(DISPUTE_STATUS_DB, "daDong"),
            "ketquaxuly": "khongCoHuHai",
            "noidungketluan": req.decisionnote,
            "txhashresolve": txs[0]["txHash"],
            "capnhatluc": now_iso(),
        })
        if report:
            report = self.update("damage_reports", "id", report["id"], {
                "trangthai": "daDong",
                "capnhatluc": now_iso(),
            })
        deposit = self.update("deposits", "id", deposit["id"], {
            "sotienhoancoc": self._to_number(locked),
            "sotienkhoacoc": 0,
            "txhashrefund": txs[1]["txHash"],
            "hethongxuly": True,
            "trangthai": self._db_status(DEPOSIT_STATUS_DB, "daHoan"),
            "capnhatluc": now_iso(),
        })
        contract = self.update("contracts", "id", contract["id"], {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "hoanThanh"),
            "txhashsettlement": txs[1]["txHash"],
            "blocknumbersettlement": block["blockHeight"],
            "tongtienhoanlai": self._to_number(locked),
            "danhanlaixe": True,
            "summaryhash": decision_hash,
            "capnhatluc": now_iso(),
        })
        self._complete_booking_for_contract(contract)
        self._refresh_vehicle_status_by_activity(contract["xeid"])
        self._log_service_event("admin_confirm_no_damage_success", disputeId=dispute_id, blockHeight=block.get("blockHeight"), refundTx=txs[1].get("txHash"), refundAmount=self._to_number(locked))
        return {"block": block, "transactions": txs, "contract": contract, "deposit": deposit, "dispute": dispute, "damageReport": report, "mirror": mine_result["mirror"]}

    def admin_confirm_damage(self, dispute_id: str, admin_id: str, req: AdminConfirmDamageRequest) -> dict:
        self._log_service_event("admin_confirm_damage_attempt", disputeId=dispute_id, adminId=admin_id, approvedCost=req.approvedcost)
        self._ensure_system_wallets()
        dispute, contract, deposit, report = self._get_dispute_bundle(dispute_id)
        self._ensure_dispute_status(dispute, ["choAdminXacMinh"], "xac nhan co hu hai")
        self._ensure_admin_user_context(admin_id)
        admin_wallet = self._require_user_wallet(admin_id, "admin")
        locked = self._locked_deposit_amount(deposit)
        approved_cost = self._decimal(req.approvedcost)
        if locked <= ZERO:
            raise ValueError("Deposit khong con so tien dang khoa de xu ly")
        if approved_cost > locked:
            raise ValueError("approvedCost vuot qua tien coc dang khoa")

        split = self._split_amount_with_fee(approved_cost)
        refund = locked - approved_cost
        escrow_address = SYSTEM_ESCROW_ADDRESS
        fee_address = PLATFORM_FEE_ADDRESS
        owner_address = contract["addresschuxe"]
        renter_address = contract["addressnguoithue"]
        self._ensure_sufficient_balance(escrow_address, locked)
        self._ensure_sufficient_locked_balance(renter_address, locked)

        payload = {
            "tranhChapId": dispute_id,
            "hopDongThueId": contract["id"],
            "adminId": admin_id,
            "approvedCost": self._to_number(approved_cost),
            "decisionNote": req.decisionnote,
            "evidenceMeta": req.evidencemeta,
            "decision": "coHuHai",
        }
        decision_hash = self._build_evidence_hash("adminDecisionDamageConfirmed", payload)
        txs = [
            self._make_tx(
                "ADMIN_DECISION_DAMAGE_CONFIRMED",
                admin_wallet["address"],
                escrow_address,
                ZERO,
                {
                    **self._money_flow_raw(
                        contract_id=contract["id"],
                        deposit_id=deposit["id"],
                        dispute_id=dispute_id,
                        business_action="adminDecisionDamageConfirmed",
                    ),
                    "baoCaoHuHaiId": report["id"] if report else None,
                    "decision": "coHuHai",
                    "decisionHash": decision_hash,
                    **payload,
                },
            ),
            self._make_tx(
                "PAYOUT_DEPOSIT_TO_OWNER",
                escrow_address,
                owner_address,
                approved_cost,
                self._money_flow_raw(
                    contract_id=contract["id"],
                    deposit_id=deposit["id"],
                    dispute_id=dispute_id,
                    business_action="damageDepositPayout",
                    gross=approved_cost,
                    fee=split["fee_amount"],
                    net=split["net_amount"],
                    extra={"decision": "coHuHai", "decisionHash": decision_hash},
                ),
            ),
            self._make_tx(
                "DAMAGE_PAYOUT_GROSS",
                escrow_address,
                owner_address,
                approved_cost,
                self._money_flow_raw(
                    contract_id=contract["id"],
                    deposit_id=deposit["id"],
                    dispute_id=dispute_id,
                    business_action="damagePayoutGross",
                    gross=approved_cost,
                    fee=split["fee_amount"],
                    net=split["net_amount"],
                ),
            ),
        ]
        if split["fee_amount"] > ZERO:
            txs.append(
                self._make_tx(
                    "PLATFORM_FEE_CHARGED",
                    escrow_address,
                    fee_address,
                    split["fee_amount"],
                    self._money_flow_raw(
                        contract_id=contract["id"],
                        deposit_id=deposit["id"],
                        dispute_id=dispute_id,
                        business_action="platformFeeChargedFromDamage",
                        gross=approved_cost,
                        fee=split["fee_amount"],
                        net=split["net_amount"],
                    ),
                )
            )
        if split["net_amount"] > ZERO:
            txs.append(
                self._make_tx(
                    "OWNER_NET_PAYOUT",
                    escrow_address,
                    owner_address,
                    split["net_amount"],
                    self._money_flow_raw(
                        contract_id=contract["id"],
                        deposit_id=deposit["id"],
                        dispute_id=dispute_id,
                        business_action="ownerNetPayoutFromDamage",
                        gross=approved_cost,
                        fee=split["fee_amount"],
                        net=split["net_amount"],
                    ),
                )
            )
        refund_tx = None
        escrow_refund_tx = None
        if refund > ZERO:
            refund_tx = self._make_tx(
                "REFUND_DEPOSIT",
                escrow_address,
                renter_address,
                refund,
                self._money_flow_raw(
                    contract_id=contract["id"],
                    deposit_id=deposit["id"],
                    dispute_id=dispute_id,
                    business_action="refundDepositRemainder",
                    gross=refund,
                    net=refund,
                    extra={"decision": "coHuHai", "decisionHash": decision_hash},
                ),
            )
            escrow_refund_tx = self._make_tx(
                "ESCROW_REFUND",
                escrow_address,
                renter_address,
                refund,
                self._money_flow_raw(
                    contract_id=contract["id"],
                    deposit_id=deposit["id"],
                    dispute_id=dispute_id,
                    business_action="escrowRefundRemainder",
                    gross=refund,
                    net=refund,
                ),
            )
            txs.extend([refund_tx, escrow_refund_tx])

        mine_result = self._mine_and_mirror(txs)
        block = mine_result["block"]

        self._update_wallet_balance(escrow_address, -locked, ZERO)
        self._update_wallet_balance(renter_address, refund, -locked)
        if split["fee_amount"] > ZERO:
            self._update_wallet_balance(fee_address, split["fee_amount"], ZERO)
        if split["net_amount"] > ZERO:
            self._update_wallet_balance(owner_address, split["net_amount"], ZERO)

        dispute = self.update("disputes", "id", dispute_id, {
            "trangthai": self._db_status(DISPUTE_STATUS_DB, "daDong"),
            "ketquaxuly": "coHuHai",
            "sotienphaithu": self._to_number(approved_cost),
            "noidungketluan": req.decisionnote,
            "txhashresolve": txs[0]["txHash"],
            "capnhatluc": now_iso(),
        })
        if report:
            report = self.update("damage_reports", "id", report["id"], {
                "chiphisua": self._to_number(approved_cost),
                "trangthai": "daDong",
                "capnhatluc": now_iso(),
            })
        deposit = self.update("deposits", "id", deposit["id"], {
            "sotienhoancoc": self._to_number(refund),
            "sotienkhoacoc": 0,
            "txhashrefund": refund_tx["txHash"] if refund_tx else None,
            "hethongxuly": True,
            "trangthai": self._db_status(DEPOSIT_STATUS_DB, "daChuyenChoOwner" if refund == ZERO else "daTatToan"),
            "capnhatluc": now_iso(),
        })
        contract = self.update("contracts", "id", contract["id"], {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "hoanThanh"),
            "txhashsettlement": txs[1]["txHash"],
            "blocknumbersettlement": block["blockHeight"],
            "tongtienhoanlai": self._to_number(refund),
            "danhanlaixe": True,
            "summaryhash": decision_hash,
            "capnhatluc": now_iso(),
        })
        self._complete_booking_for_contract(contract)
        self._refresh_vehicle_status_by_activity(contract["xeid"])
        self._log_service_event("admin_confirm_damage_success", disputeId=dispute_id, blockHeight=block.get("blockHeight"), gross=self._to_number(approved_cost), fee=self._to_number(split["fee_amount"]), net=self._to_number(split["net_amount"]), refund=self._to_number(refund))
        return {"block": block, "transactions": txs, "contract": contract, "deposit": deposit, "dispute": dispute, "damageReport": report, "mirror": mine_result["mirror"]}

    def settle_contract(self, contract_id: str, tong_tien_thanh_toan: float, tong_tien_hoan_lai: float) -> dict:
        self._log_service_event("settle_contract_attempt", contractId=contract_id, tongTienThanhToan=tong_tien_thanh_toan, tongTienHoanLai=tong_tien_hoan_lai)
        self._ensure_system_wallets()
        contract, deposit = self._get_contract_and_deposit(contract_id)
        existing_settlement_txs = (
            self.t("transactions")
            .select("txhash,txtype")
            .eq("hopdongthueid", contract_id)
            .in_("txtype", ["SETTLE_PAYMENT", "RENTAL_PAYMENT_GROSS", "PAYOUT_DEPOSIT_TO_OWNER", "REFUND_DEPOSIT"])
            .limit(1)
            .execute()
            .data
            or []
        )
        if existing_settlement_txs:
            raise ValueError("Contract da co giao dich tat toan truoc do. Vui long refresh du lieu truoc khi thu lai")
        if self._has_open_dispute(contract_id):
            raise ValueError("Contract dang tranh chap, khong the tat toan truc tiep")
        if contract.get("trangthai") != self._db_status(CONTRACT_STATUS_DB, "dangThue"):
            raise ValueError("Chi duoc tat toan khi hop dong dang o trang thai cho tat toan")
        if not bool(contract.get("danhanlaixe")):
            raise ValueError("Chu xe chua xac nhan nhan lai xe, khong the tat toan")

        rental_gross = self._decimal(tong_tien_thanh_toan)
        refund = self._decimal(tong_tien_hoan_lai)
        locked = self._locked_deposit_amount(deposit)
        if refund > locked:
            raise ValueError("Tong tien hoan lai vuot qua tien coc dang khoa")
        deposit_payout_gross = locked - refund

        renter_address = contract["addressnguoithue"]
        owner_address = contract["addresschuxe"]
        escrow_address = SYSTEM_ESCROW_ADDRESS
        fee_address = PLATFORM_FEE_ADDRESS
        if rental_gross > ZERO:
            self._ensure_sufficient_balance(renter_address, rental_gross)
        if locked > ZERO:
            self._ensure_sufficient_balance(escrow_address, locked)
            self._ensure_sufficient_locked_balance(renter_address, locked)

        rental_split = self._split_amount_with_fee(rental_gross)
        deposit_split = self._split_amount_with_fee(deposit_payout_gross) if deposit_payout_gross > ZERO else {"gross_amount": ZERO, "fee_amount": ZERO, "net_amount": ZERO}

        txs = [
            self._make_tx(
                "SETTLE_PAYMENT",
                renter_address,
                owner_address,
                rental_gross,
                self._money_flow_raw(
                    contract_id=contract_id,
                    deposit_id=deposit["id"],
                    dispute_id=None,
                    business_action="settlePayment",
                    gross=rental_gross,
                    fee=rental_split["fee_amount"],
                    net=rental_split["net_amount"],
                    extra={"action": "tatToan"},
                ),
            )
        ]
        if rental_gross > ZERO:
            txs.append(self._make_tx("RENTAL_PAYMENT_GROSS", renter_address, owner_address, rental_gross, self._money_flow_raw(contract_id=contract_id, deposit_id=deposit["id"], dispute_id=None, business_action="rentalPaymentGross", gross=rental_gross, fee=rental_split["fee_amount"], net=rental_split["net_amount"])))
            if rental_split["fee_amount"] > ZERO:
                txs.append(self._make_tx("PLATFORM_FEE_CHARGED", renter_address, fee_address, rental_split["fee_amount"], self._money_flow_raw(contract_id=contract_id, deposit_id=deposit["id"], dispute_id=None, business_action="platformFeeChargedFromRental", gross=rental_gross, fee=rental_split["fee_amount"], net=rental_split["net_amount"])))
            if rental_split["net_amount"] > ZERO:
                txs.append(self._make_tx("OWNER_NET_PAYOUT", renter_address, owner_address, rental_split["net_amount"], self._money_flow_raw(contract_id=contract_id, deposit_id=deposit["id"], dispute_id=None, business_action="ownerNetPayoutFromRental", gross=rental_gross, fee=rental_split["fee_amount"], net=rental_split["net_amount"])))

        refund_tx = None
        if deposit_payout_gross > ZERO:
            txs.append(self._make_tx("PAYOUT_DEPOSIT_TO_OWNER", escrow_address, owner_address, deposit_payout_gross, self._money_flow_raw(contract_id=contract_id, deposit_id=deposit["id"], dispute_id=None, business_action="settleDepositPayout", gross=deposit_payout_gross, fee=deposit_split["fee_amount"], net=deposit_split["net_amount"])))
            if deposit_split["fee_amount"] > ZERO:
                txs.append(self._make_tx("PLATFORM_FEE_CHARGED", escrow_address, fee_address, deposit_split["fee_amount"], self._money_flow_raw(contract_id=contract_id, deposit_id=deposit["id"], dispute_id=None, business_action="platformFeeChargedFromDepositPayout", gross=deposit_payout_gross, fee=deposit_split["fee_amount"], net=deposit_split["net_amount"])))
            if deposit_split["net_amount"] > ZERO:
                txs.append(self._make_tx("OWNER_NET_PAYOUT", escrow_address, owner_address, deposit_split["net_amount"], self._money_flow_raw(contract_id=contract_id, deposit_id=deposit["id"], dispute_id=None, business_action="ownerNetPayoutFromDeposit", gross=deposit_payout_gross, fee=deposit_split["fee_amount"], net=deposit_split["net_amount"])))
        if refund > ZERO:
            refund_tx = self._make_tx("REFUND_DEPOSIT", escrow_address, renter_address, refund, self._money_flow_raw(contract_id=contract_id, deposit_id=deposit["id"], dispute_id=None, business_action="refundDeposit", gross=refund, net=refund))
            txs.append(refund_tx)
            txs.append(self._make_tx("ESCROW_REFUND", escrow_address, renter_address, refund, self._money_flow_raw(contract_id=contract_id, deposit_id=deposit["id"], dispute_id=None, business_action="escrowRefund", gross=refund, net=refund)))

        mine_result = self._mine_and_mirror(txs)
        block = mine_result["block"]

        if rental_gross > ZERO:
            self._update_wallet_balance(renter_address, -rental_gross, ZERO)
            if rental_split["fee_amount"] > ZERO:
                self._update_wallet_balance(fee_address, rental_split["fee_amount"], ZERO)
            if rental_split["net_amount"] > ZERO:
                self._update_wallet_balance(owner_address, rental_split["net_amount"], ZERO)
        if locked > ZERO:
            self._update_wallet_balance(escrow_address, -locked, ZERO)
            self._update_wallet_balance(renter_address, refund, -locked)
            if deposit_split["fee_amount"] > ZERO:
                self._update_wallet_balance(fee_address, deposit_split["fee_amount"], ZERO)
            if deposit_split["net_amount"] > ZERO:
                self._update_wallet_balance(owner_address, deposit_split["net_amount"], ZERO)

        contract = self.update("contracts", "id", contract_id, {
            "trangthai": self._db_status(CONTRACT_STATUS_DB, "hoanThanh"),
            "tongtienthanhtoan": self._to_number(rental_gross),
            "tongtienhoanlai": self._to_number(refund),
            "txhashsettlement": txs[0]["txHash"],
            "blocknumbersettlement": block["blockHeight"],
            "danhanlaixe": True,
            "capnhatluc": now_iso(),
        })
        deposit = self.update("deposits", "id", deposit["id"], {
            "sotienhoancoc": self._to_number(refund),
            "sotienkhoacoc": 0,
            "txhashrefund": refund_tx["txHash"] if refund_tx else None,
            "hethongxuly": True,
            "trangthai": self._db_status(DEPOSIT_STATUS_DB, "daHoan" if refund > ZERO and deposit_payout_gross == ZERO else "daTatToan"),
            "capnhatluc": now_iso(),
        })
        self._complete_booking_for_contract(contract)
        self._refresh_vehicle_status_by_activity(contract["xeid"])
        self._log_service_event("settle_contract_success", contractId=contract_id, blockHeight=block.get("blockHeight"), rentalGross=self._to_number(rental_gross), rentalFee=self._to_number(rental_split["fee_amount"]), rentalNet=self._to_number(rental_split["net_amount"]), depositPayoutGross=self._to_number(deposit_payout_gross), refund=self._to_number(refund))
        return {"block": block, "transactions": txs, "hopDongThue": contract, "tienCoc": deposit, "mirror": mine_result["mirror"]}

    def wallets_overview(self) -> dict:
        self._ensure_system_wallets()
        wallets = self.t("wallets").select("*").limit(200).execute().data or []
        users = self.t("users").select("*").limit(200).execute().data or []
        user_map = {row.get("id"): row for row in users}
        items = []
        for wallet in wallets:
            owner = user_map.get(wallet.get("nguoidungid"))
            items.append({
                "id": wallet.get("id"),
                "address": wallet.get("address"),
                "walletType": wallet.get("wallettype"),
                "status": wallet.get("status"),
                "balance": self._to_number(wallet.get("balance")),
                "lockedBalance": self._to_number(wallet.get("lockedbalance")),
                "owner": None if owner is None else {
                    "id": owner.get("id"),
                    "hoTen": owner.get("hoten"),
                    "email": owner.get("email"),
                    "soDienThoai": owner.get("sodienthoai"),
                    "vaiTro": owner.get("vaitro"),
                },
            })
        return {"wallets": items, "systemWallets": {"escrowAddress": self._normalize_address(SYSTEM_ESCROW_ADDRESS), "platformFeeAddress": self._normalize_address(PLATFORM_FEE_ADDRESS)}}

    def finance_transactions(self, *, wallet_address: Optional[str] = None, tx_type: Optional[str] = None, contract_id: Optional[str] = None, dispute_id: Optional[str] = None) -> dict:
        rows = self.t("transactions").select("*").order("timestamp", desc=True).limit(500).execute().data or []
        filtered = []
        address_filter = self._normalize_address(wallet_address) if wallet_address else None
        for row in rows:
            raw = row.get("rawdata") or {}
            from_address = self._normalize_address(row.get("fromaddress"))
            to_address = self._normalize_address(row.get("toaddress"))
            if address_filter and address_filter not in {from_address, to_address}:
                continue
            if tx_type and row.get("txtype") != tx_type:
                continue
            if contract_id and row.get("hopdongthueid") != contract_id and raw.get("hopDongThueId") != contract_id:
                continue
            if dispute_id and row.get("tranhchapid") != dispute_id and raw.get("tranhChapId") != dispute_id:
                continue
            filtered.append({
                "txHash": row.get("txhash"),
                "txType": row.get("txtype"),
                "fromAddress": row.get("fromaddress"),
                "toAddress": row.get("toaddress"),
                "amount": self._to_number(row.get("amount")),
                "timestamp": row.get("timestamp"),
                "blockHeight": row.get("blockheight"),
                "blockHash": row.get("blockhash"),
                "contractId": row.get("hopdongthueid") or raw.get("hopDongThueId"),
                "depositId": row.get("tiencocid") or raw.get("tienCocId"),
                "disputeId": row.get("tranhchapid") or raw.get("tranhChapId"),
                "rawData": raw,
            })
        return {"filters": {"walletAddress": address_filter, "txType": tx_type, "contractId": contract_id, "disputeId": dispute_id}, "transactions": filtered, "count": len(filtered)}

    def finance_summary(self) -> dict:
        rows = self.t("transactions").select("*").limit(1000).execute().data or []
        totals = {
            "totalPlatformFeesCollected": ZERO,
            "totalRentalGross": ZERO,
            "totalOwnerNetPayout": ZERO,
            "totalDepositLocked": ZERO,
            "totalDepositRefunded": ZERO,
            "totalDamageGross": ZERO,
            "totalGrossPayments": ZERO,
            "totalNetPayouts": ZERO,
        }
        for row in rows:
            tx_type = row.get("txtype")
            amount = self._decimal(row.get("amount"))
            if tx_type == "PLATFORM_FEE_CHARGED":
                totals["totalPlatformFeesCollected"] += amount
            elif tx_type == "RENTAL_PAYMENT_GROSS":
                totals["totalRentalGross"] += amount
                totals["totalGrossPayments"] += amount
            elif tx_type == "OWNER_NET_PAYOUT":
                totals["totalOwnerNetPayout"] += amount
                totals["totalNetPayouts"] += amount
            elif tx_type == "ESCROW_LOCK":
                totals["totalDepositLocked"] += amount
            elif tx_type == "ESCROW_REFUND":
                totals["totalDepositRefunded"] += amount
            elif tx_type == "DAMAGE_PAYOUT_GROSS":
                totals["totalDamageGross"] += amount
                totals["totalGrossPayments"] += amount
        latest_block, latest_block_error = self._safe_db_latest_block_meta()
        return {
            **{key: self._to_number(value) for key, value in totals.items()},
            "totalTransactions": len(rows),
            "latestBlock": latest_block,
            "warnings": {} if latest_block_error is None else {"latestBlock": latest_block_error},
            "platformFeeRate": PLATFORM_FEE_RATE,
            "systemWallets": {"escrowAddress": self._normalize_address(SYSTEM_ESCROW_ADDRESS), "platformFeeAddress": self._normalize_address(PLATFORM_FEE_ADDRESS)},
        }

    def contract_money_flow(self, contract_id: str) -> dict:
        transactions = self.finance_transactions(contract_id=contract_id)["transactions"]
        rows = self.t("events").select("*").limit(500).execute().data or []
        events = []
        for row in rows:
            data = row.get("data") or {}
            if data.get("hopDongThueId") == contract_id:
                events.append({
                    "eventId": row.get("eventid"),
                    "eventName": row.get("eventname"),
                    "blockHeight": row.get("blockheight"),
                    "blockHash": row.get("blockhash"),
                    "createdAt": row.get("createdat"),
                    "data": data,
                })
        return {
            "contractId": contract_id,
            "transactions": transactions,
            "events": events,
            "summary": {
                "transactionCount": len(transactions),
                "eventCount": len(events),
                "grossPayments": self._to_number(sum(self._decimal(tx["amount"]) for tx in transactions if tx["txType"] in {"RENTAL_PAYMENT_GROSS", "DAMAGE_PAYOUT_GROSS"})),
                "fees": self._to_number(sum(self._decimal(tx["amount"]) for tx in transactions if tx["txType"] == "PLATFORM_FEE_CHARGED")),
                "netPayouts": self._to_number(sum(self._decimal(tx["amount"]) for tx in transactions if tx["txType"] == "OWNER_NET_PAYOUT")),
                "refunds": self._to_number(sum(self._decimal(tx["amount"]) for tx in transactions if tx["txType"] == "ESCROW_REFUND")),
            },
        }

    def overview(self) -> dict:
        chain = self.node.export_chain()
        blocks = chain.get("blocks", [])
        local_meta = chain.get("meta", {})
        db_latest, db_latest_error = self._safe_db_latest_block_meta()
        local_height = local_meta.get("latestBlockHeight")
        local_hash = local_meta.get("latestBlockHash")
        db_height = db_latest.get("blockheight")
        db_hash = db_latest.get("hash")
        sync_status = "localOnly" if db_height is None and db_hash is None else ("synced" if local_height == db_height and local_hash == db_hash else "outOfSync")
        payload = {"users": [], "wallets": [], "vehicles": [], "bookings": [], "contracts": [], "deposits": [], "damageReports": [], "disputes": [], "transactions": [], "events": []}
        warnings = {}
        try:
            self._ensure_system_wallets()
        except Exception as exc:
            warnings["systemWallets"] = str(exc)
        for response_key, table_key in [("users", "users"), ("wallets", "wallets"), ("vehicles", "vehicles"), ("bookings", "bookings"), ("contracts", "contracts"), ("deposits", "deposits"), ("damageReports", "damage_reports"), ("disputes", "disputes"), ("transactions", "transactions"), ("events", "events")]:
            rows, error = self.safe_list_rows(table_key, 30)
            payload[response_key] = rows
            if error:
                warnings[response_key] = error
        if db_latest_error:
            warnings["dbLatestBlock"] = db_latest_error
        wallet_rows = payload["wallets"]
        total_wallet_balance = ZERO
        total_locked_balance = ZERO
        for row in wallet_rows:
            try:
                total_wallet_balance += self._decimal(row.get("balance"))
                total_locked_balance += self._decimal(row.get("lockedbalance"))
            except Exception as exc:
                warnings["walletBalances"] = str(exc)
                break

        fee_wallet_balance = ZERO
        escrow_wallet_balance = ZERO
        try:
            fee_wallet = self._get_wallet_by_address(PLATFORM_FEE_ADDRESS)
            if fee_wallet:
                fee_wallet_balance = self._decimal(fee_wallet.get("balance"))
        except Exception as exc:
            warnings["platformFeeWallet"] = str(exc)
        try:
            escrow_wallet = self._get_wallet_by_address(SYSTEM_ESCROW_ADDRESS)
            if escrow_wallet:
                escrow_wallet_balance = self._decimal(escrow_wallet.get("balance"))
        except Exception as exc:
            warnings["escrowWallet"] = str(exc)

        finance = {
            "totalPlatformFeesCollected": 0.0,
            "totalGrossPayments": 0.0,
            "totalNetPayouts": 0.0,
        }
        try:
            finance = self.finance_summary()
        except Exception as exc:
            warnings["financeSummary"] = str(exc)
        return {
            **payload,
            "warnings": warnings,
            "localLatestBlockHeight": local_height,
            "localLatestBlockHash": local_hash,
            "dbLatestBlockHeight": db_height,
            "dbLatestBlockHash": db_hash,
            "syncStatus": sync_status,
            "nodeChainMeta": local_meta,
            "latestBlock": blocks[-1] if blocks else None,
            "chain": chain,
            "platformFeeWalletBalance": self._to_number(fee_wallet_balance),
            "escrowWalletBalance": self._to_number(escrow_wallet_balance),
            "totalWalletBalance": self._to_number(total_wallet_balance),
            "totalLockedBalance": self._to_number(total_locked_balance),
            "totalFeesCollected": finance["totalPlatformFeesCollected"],
            "totalGrossPayments": finance["totalGrossPayments"],
            "totalNetPayouts": finance["totalNetPayouts"],
            "platformFeeRate": PLATFORM_FEE_RATE,
        }

