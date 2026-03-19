from pprint import pprint

from Account import AccountState
from Blockchain import Blockchain
from Service.HashService import sha256_text
from Service.RentalService import RentalService


def nhap_so_thuc(thong_bao: str, mac_dinh: float | None = None) -> float:
    while True:
        gia_tri = input(thong_bao).strip()
        if not gia_tri and mac_dinh is not None:
            return float(mac_dinh)
        try:
            return float(gia_tri)
        except ValueError:
            print("Gia tri khong hop le, vui long nhap so.")


def nhap_so_nguyen(thong_bao: str, mac_dinh: int | None = None) -> int:
    while True:
        gia_tri = input(thong_bao).strip()
        if not gia_tri and mac_dinh is not None:
            return int(mac_dinh)
        try:
            return int(gia_tri)
        except ValueError:
            print("Gia tri khong hop le, vui long nhap so nguyen.")


def nhap_yes_no(thong_bao: str) -> bool:
    while True:
        lua_chon = input(thong_bao).strip().lower()
        if lua_chon in ("y", "yes"):
            return True
        if lua_chon in ("n", "no"):
            return False
        print("Vui long nhap y hoac n.")


def in_tieu_de(tieu_de: str) -> None:
    print("\n" + "=" * 60)
    print(tieu_de)
    print("=" * 60)


def tao_dia_chi_vi(owner_name: str, vai_tro: str, secret: str) -> str:
    seed = f"{owner_name}|{vai_tro}|{secret}"
    return "0x" + sha256_text(seed)[:16].upper()


def tao_tai_khoan_nguoi_dung(vai_tro: str) -> tuple[AccountState, str]:
    in_tieu_de(f"NHAP THONG TIN {vai_tro}")

    owner_name = input("Ten chu tai khoan: ").strip()
    balance = nhap_so_thuc("So du ban dau: ")
    secret = input("Mat khau/secret de ky giao dich: ").strip()
    address = tao_dia_chi_vi(owner_name, vai_tro, secret)

    account = AccountState(
        address=address,
        ownerName=owner_name,
        role=vai_tro,
        balance=balance,
    )
    return account, secret


def nhap_thong_tin_hop_dong() -> dict:
    in_tieu_de("NHAP THONG TIN HOP DONG THUE")

    return {
        "contractId": input("Ma hop dong (vd: RC001): ").strip(),
        "bookingId": input("Ma dat xe (vd: BK001): ").strip(),
        "vehicleId": input("Ma xe (vd: CAR001): ").strip(),
        "depositAmount": nhap_so_thuc("Tien coc: "),
    }


def nhap_thong_tin_su_dung() -> tuple[dict, float, float, float, float]:
    in_tieu_de("NHAP THONG TIN TRA XE / SU DUNG XE")

    total_km = nhap_so_thuc("Tong so km da di: ", 0)
    total_hours = nhap_so_thuc("Tong so gio su dung: ", 0)
    late_minutes = nhap_so_nguyen("So phut tra tre: ", 0)
    fuel_percent = nhap_so_thuc("Muc nhien lieu con lai (%): ", 100)
    ghi_chu = input("Ghi chu: ").strip()

    base_price = nhap_so_thuc("Tien thue co ban: ", 0)
    overtime_fee = nhap_so_thuc("Phi qua gio: ", 0)
    fuel_fee = nhap_so_thuc("Phi nhien lieu: ", 0)
    damage_fee = nhap_so_thuc("Phi hu hong: ", 0)

    usage_summary = {
        "totalKm": total_km,
        "totalHours": total_hours,
        "lateMinutes": late_minutes,
        "fuelPercent": fuel_percent,
        "note": ghi_chu,
    }

    return usage_summary, base_price, overtime_fee, fuel_fee, damage_fee


def hien_thi_tom_tat_chain(blockchain: Blockchain) -> None:
    in_tieu_de("TOM TAT CHAIN")
    print(f"Chain ID: {blockchain.chainId}")
    print(f"So block: {len(blockchain.chain)}")
    print(f"So giao dich pending: {len(blockchain.pendingTransactions)}")
    print(f"Chain hop le: {blockchain.is_chain_valid()}")

    print("\n--- ACCOUNTS ---")
    for acc in blockchain.accounts.values():
        pprint(acc.to_dict())

    print("\n--- CONTRACTS ---")
    for contract in blockchain.contracts.values():
        pprint(contract.to_dict())

    print("\n--- BLOCKS ---")
    for block in blockchain.chain:
        print(
            f"Block #{block.blockNumber} | "
            f"hash={block.blockHash[:16]}... | "
            f"prev={block.previousHash[:16]}... | "
            f"txCount={len(block.transactions)}"
        )


def main():
    in_tieu_de("HE THONG THUE XE TU LAI THANH TOAN TU DONG - DEMO TERMINAL")

    blockchain = Blockchain(chainId="carRentalAutoPayment")
    rental_service = RentalService(blockchain)

    # 1) Tao 2 tai khoan
    renter, renter_secret = tao_tai_khoan_nguoi_dung("RENTER")
    owner, owner_secret = tao_tai_khoan_nguoi_dung("OWNER")

    blockchain.register_account(renter)
    blockchain.register_account(owner)

    in_tieu_de("DA TAO TAI KHOAN")
    pprint(renter.to_dict())
    pprint(owner.to_dict())

    # 2) Tao hop dong
    hop_dong_input = nhap_thong_tin_hop_dong()

    contract = rental_service.create_contract(
        contract_id=hop_dong_input["contractId"],
        booking_id=hop_dong_input["bookingId"],
        vehicle_id=hop_dong_input["vehicleId"],
        renter_address=renter.address,
        owner_address=owner.address,
        deposit_amount=hop_dong_input["depositAmount"],
    )

    in_tieu_de("DA TAO HOP DONG")
    pprint(contract.to_dict())

    # 3) Khoa coc
    if nhap_yes_no("Xac nhan khoa tien coc? (y/n): "):
        try:
            lock_tx = rental_service.lock_deposit(contract.contractId, renter_secret)

            in_tieu_de("GIAO DICH KHOA COC")
            pprint(lock_tx.to_dict())

            if nhap_yes_no("Mine block cho giao dich khoa coc? (y/n): "):
                block1 = blockchain.mine_pending_transactions(validatorAddress="0xVALIDATOR001")
                in_tieu_de("DA MINE BLOCK KHOA COC")
                pprint(block1.to_dict() if block1 else None)

        except Exception as e:
            in_tieu_de("LOI KHI KHOA COC")
            print(str(e))
            return
    else:
        print("Ban da huy qua trinh.")
        return

    # 4) Nhap thong tin tra xe / usage
    usage_summary, base_price, overtime_fee, fuel_fee, damage_fee = nhap_thong_tin_su_dung()

    rental_service.record_usage(contract.contractId, usage_summary)

    in_tieu_de("DA GHI NHAN THONG TIN SU DUNG")
    pprint(contract.to_dict())

    # 5) Tat toan hop dong
    if nhap_yes_no("Xac nhan tat toan hop dong? (y/n): "):
        try:
            settlement_txs = rental_service.settle_contract(
                contract_id=contract.contractId,
                renter_secret=renter_secret,
                base_price=base_price,
                overtime_fee=overtime_fee,
                fuel_fee=fuel_fee,
                damage_fee=damage_fee,
            )

            in_tieu_de("CAC GIAO DICH TAT TOAN")
            for tx in settlement_txs:
                pprint(tx.to_dict())

            if nhap_yes_no("Mine block cho tat toan? (y/n): "):
                block2 = blockchain.mine_pending_transactions(validatorAddress="0xVALIDATOR001")
                in_tieu_de("DA MINE BLOCK TAT TOAN")
                pprint(block2.to_dict() if block2 else None)

        except Exception as e:
            in_tieu_de("LOI KHI TAT TOAN")
            print(str(e))
            return
    else:
        print("Hop dong chua duoc tat toan.")
        hien_thi_tom_tat_chain(blockchain)
        return

    # 6) Xuat chain
    output_path = "data/chain.json"
    blockchain.export_to_json(output_path)

    in_tieu_de("KET QUA CUOI CUNG")
    hien_thi_tom_tat_chain(blockchain)

    print(f"\nDa xuat chain ra file: {output_path}")


if __name__ == "__main__":
    main()