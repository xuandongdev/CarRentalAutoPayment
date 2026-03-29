# CarRentalAutoPayment - Backend2 Hybrid Demo

`backend2` la phien ban backend demo cho bai toan thue xe co ket hop:
- blockchain local de luu vet audit bat bien
- Supabase de luu du lieu nghiep vu, query va bao cao
- auth theo user/password va lien ket vi MetaMask off-chain
- ledger dong tien co tinh phi nen tang 10%

README nay mo ta dung flow hien tai cua `backend2`, khong mo ta flow cu trong `backend/`.

## 1. Tong quan kien truc

He thong dung mo hinh hybrid 2 lop:

1. Local blockchain trong `backend2/NodeData`
- Moi buoc tai chinh hoac phap ly quan trong deu tao local transaction
- Sau do mine block local
- Block va transaction duoc luu thanh file JSON de audit

2. Supabase cho nghiep vu va mirror
- Luu `NguoiDung`, `Wallet`, `Xe`, `DangKy`, `HopDongThue`, `TienCoc`, `BaoCaoHuHai`, `TranhChap`
- Dong thoi mirror `Block`, `Transaction`, `Event` de lam overview, report va finance dashboard

Noi ngan gon:
- `NodeData` la so cai bat bien de xem lai lich su
- Supabase la nguon de frontend truy van nhanh va hien thi tong hop

## 2. Cau truc `backend2`

### Backend
- `backend2/server.py`: bootstrap FastAPI, route auth, route nghiep vu, mount static `/frontend`
- `backend2/modules/auth.py`: register, login, logout, `/auth/me`, lien ket MetaMask, session token
- `backend2/modules/service.py`: toan bo logic booking, contract, deposit, dispute, finance, mirror chain
- `backend2/modules/config.py`: doc env, dia chi vi he thong, fee rate, ten bang
- `backend2/modules/node_storage.py`: doc/ghi local chain trong `NodeData`
- `backend2/modules/html_page.py`: route `/` de dan huong vao cac trang frontend

### Frontend
- `frontend/auth.html`: dang ky, dang nhap, lien ket MetaMask
- `frontend/owner.html`: giao dien chu xe
- `frontend/renter.html`: giao dien khach thue
- `frontend/admin.html`: giao dien quan tri tranh chap
- `frontend/finance.html`: giao dien xem vi, tong hop tai chinh, dong tien theo hop dong
- `frontend/index.html`: bang dieu khien tong hop de test end-to-end

## 3. 3 role va phan quyen

He thong co 3 vai tro chinh trong bang `NguoiDung.vaiTro`:

- `admin`
- `chuXe`
- `khach`

Phan quyen hien tai trong `backend2`:

### `khach`
- tao booking bang tai khoan cua minh
- tao contract tu booking cua minh
- lock deposit cho contract minh thue
- return vehicle cho contract minh thue
- xem money flow cua contract minh tham gia

### `chuXe`
- them xe bang tai khoan cua minh
- tao damage claim cho contract minh so huu
- xem money flow cua contract minh so huu
- co the settle contract lien quan neu khong tranh chap

### `admin`
- xem tong quan he thong
- xem wallets overview, finance summary, finance transactions
- reconcile local chain voi Supabase
- admin confirm no damage
- admin confirm damage
- xem tat ca contract money flow

Frontend cung an/hien nav va card theo role hien tai de de test login/logout nhieu tai khoan.

## 4. Auth va lien ket vi

`backend2` ho tro 2 lop xac thuc:

1. Dang nhap truyen thong
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`

Dang nhap bang:
- `email + password`
- hoac `soDienThoai + password`

2. Lien ket MetaMask off-chain
- `POST /auth/wallet/nonce`
- frontend ky message bang `personal_sign`
- `POST /auth/wallet/verify`
- `POST /auth/wallet/unlink`

Quan trong:
- khong co login on-chain
- khong luu private key
- chi verify chu ky off-chain theo SIWE-style challenge

## 5. Vi he thong va fee 10%

He thong dung 2 vi he thong:

- `SYSTEM_ESCROW_ADDRESS`: giu tien coc
- `PLATFORM_FEE_ADDRESS`: nhan phi nen tang

Chinh sach phi:
- fee rate co dinh = `10%`
- chi thu fee tren giao dich sinh doanh thu:
  - `SETTLE_PAYMENT`
  - `PAYOUT_DEPOSIT_TO_OWNER`
- khong thu fee tren:
  - `LOCK_DEPOSIT`
  - `REFUND_DEPOSIT`

Cach hieu so du:
- `Wallet.balance`: so du kha dung
- `Wallet.lockedBalance`: phan tien dang bi khoa lam tien coc

Luu y:
> Deposit/withdraw real payment gateway not implemented; balances are seeded manually for blockchain flow testing.

Nghia la de demo, ban se tu cap nhat `Wallet.balance` truc tiep trong Supabase web truoc khi test flow.

## 6. Flow nghiep vu chinh cua backend2

## 6.1. Chu xe them xe

API:
- `POST /api/vehicles`

Flow:
1. `chuXe` dang nhap
2. gui thong tin xe
3. backend tim user owner theo email dang dung
4. tao ban ghi trong `Xe`

Buoc nay chua mine block vi day la thao tac nghiep vu thong thuong.

## 6.2. Khach tao booking

API:
- `POST /api/bookings`

Flow:
1. `khach` dang nhap
2. chon xe theo bien so
3. backend tao ban ghi trong `DangKy`
4. dat `trangThai = daDuyet`

Buoc nay chua mine block.

## 6.3. Tao contract tu booking

API:
- `POST /api/contracts/create`

Flow:
1. backend doc booking `DangKy`
2. doc `Xe`
3. doc thong tin `NguoiDung` renter va owner
4. doc wallet renter va owner
5. tao `HopDongThue`
6. tao `TienCoc`
7. cap nhat booking thanh `daTaoHopDong`

Buoc nay tao du lieu nghiep vu, chua co block rieng cho create contract.

## 6.4. Khoa tien coc

API:
- `POST /api/contracts/{contract_id}/lock-deposit`

Dieu kien:
- contract dang o khoi tao
- deposit dang `chuaKhoa`
- renter phai du `Wallet.balance`

Xu ly:
1. tao tx nghiep vu `LOCK_DEPOSIT`
2. tao tx dong tien `ESCROW_LOCK`
3. mine 1 block local
4. mirror sang Supabase
5. cap nhat vi:
- renter `balance -= deposit`
- renter `lockedBalance += deposit`
- escrow `balance += deposit`

Vi du block that tu `backend2/NodeData/Blocks/000016.json`:

```json
{
  "blockHeight": 16,
  "transactionCount": 2,
  "transactions": [
    {
      "txType": "LOCK_DEPOSIT",
      "fromAddress": "0xc8f26d3b980286b752fabdbc19aabcfe9c3b76ff",
      "toAddress": "0xSYSTEMESCROW",
      "amount": 2000000.0,
      "rawData": {
        "businessAction": "lockDeposit",
        "grossAmount": 2000000.0,
        "feeAmount": 0.0,
        "netAmount": 2000000.0
      }
    },
    {
      "txType": "ESCROW_LOCK",
      "fromAddress": "0xc8f26d3b980286b752fabdbc19aabcfe9c3b76ff",
      "toAddress": "0xSYSTEMESCROW",
      "amount": 2000000.0,
      "rawData": {
        "businessAction": "escrowLock"
      }
    }
  ]
}
```

## 6.5. Khach tra xe

API:
- `POST /api/contracts/{contract_id}/return-vehicle`

Dieu kien:
- contract dang trong giai doan thue
- nguoi tra phai la renter cua contract

Xu ly:
1. tao `evidenceHash`
2. tao tx `VEHICLE_RETURNED`
3. mine block local
4. mirror sang Supabase
5. danh dau contract da nhan lai xe

Vi du block that tu `backend2/NodeData/Blocks/000017.json`:

```json
{
  "blockHeight": 17,
  "transactionCount": 1,
  "transactions": [
    {
      "txType": "VEHICLE_RETURNED",
      "amount": 0.0,
      "rawData": {
        "action": "traXe",
        "evidenceHash": "d22ba589f6ccfde1304a37961c8796e96766aba72a08b25feacdb6a83287c4cd",
        "nguoiTraId": "6a75b40b-f0d7-45af-a37f-618da1bcafbe",
        "ghiChu": "Khach da tra xe"
      }
    }
  ]
}
```

## 6.6. Chu xe khiu nai hu hai

API:
- `POST /api/contracts/{contract_id}/damage-claim`

Dieu kien:
- xe da duoc tra
- owner dung voi contract
- deposit dang khoa
- chua co dispute mo cho contract

Xu ly:
1. tao `BaoCaoHuHai`
2. tao `TranhChap`
3. tao tx `DAMAGE_CLAIMED`
4. mine block local
5. mirror sang Supabase

Vi du block that tu `backend2/NodeData/Blocks/000018.json`:

```json
{
  "blockHeight": 18,
  "transactionCount": 1,
  "transactions": [
    {
      "txType": "DAMAGE_CLAIMED",
      "fromAddress": "0x6a358cd67cc4e28df816316df1938b2810f0fca4",
      "toAddress": "0xSYSTEMESCROW",
      "amount": 0.0,
      "rawData": {
        "tranhChapId": "5a6e6914-ccfd-4b4b-b40b-ee3142058f0b",
        "baoCaoHuHaiId": "f44fd8f5-88b9-4429-8cda-e209931f881c",
        "lyDo": "Be den",
        "estimatedCost": 15000000.0
      }
    }
  ]
}
```

## 6.7. Admin xac nhan khong hu hai

API:
- `POST /api/disputes/{dispute_id}/admin-confirm-no-damage`

Xu ly:
1. tao tx `ADMIN_DECISION_NO_DAMAGE`
2. tao tx `REFUND_DEPOSIT`
3. tao tx `ESCROW_REFUND`
4. mine block local
5. cap nhat vi:
- escrow `balance -= locked deposit`
- renter `balance += locked deposit`
- renter `lockedBalance -= locked deposit`
6. dong dispute va contract hoan thanh

Nhanh nay khong thu fee vi day la hoan coc.

## 6.8. Admin xac nhan co hu hai

API:
- `POST /api/disputes/{dispute_id}/admin-confirm-damage`

Dieu kien:
- `approvedCost <= so tien coc dang khoa`

Xu ly:
1. `approvedCost` duoc coi la `gross damage payout`
2. tinh:
- `fee = 10%`
- `ownerNet = gross - fee`
3. tao cac tx cap nghiep vu va cap dong tien
4. mine block local
5. cap nhat vi:
- escrow giam theo tong payout
- fee wallet tang fee
- owner tang `ownerNet`
- renter nhan refund neu con du deposit

Vi du block that tu `backend2/NodeData/Blocks/000019.json`:

```json
{
  "blockHeight": 19,
  "transactionCount": 5,
  "transactions": [
    {
      "txType": "ADMIN_DECISION_DAMAGE_CONFIRMED",
      "rawData": {
        "decision": "coHuHai",
        "approvedCost": 2000000.0,
        "adminId": "ecb36aa2-4e24-4648-8280-cec6fe0264e0"
      }
    },
    {
      "txType": "PAYOUT_DEPOSIT_TO_OWNER",
      "amount": 2000000.0,
      "rawData": {
        "grossAmount": 2000000.0,
        "feeAmount": 200000.0,
        "netAmount": 1800000.0
      }
    },
    {
      "txType": "DAMAGE_PAYOUT_GROSS",
      "amount": 2000000.0
    },
    {
      "txType": "PLATFORM_FEE_CHARGED",
      "toAddress": "0xPLATFORMFEE",
      "amount": 200000.0
    },
    {
      "txType": "OWNER_NET_PAYOUT",
      "toAddress": "0x6a358cd67cc4e28df816316df1938b2810f0fca4",
      "amount": 1800000.0
    }
  ]
}
```

Day la vi du ro nhat cho viec blockchain local dang ghi nhan du `gross / fee / net` trong cung mot quyet dinh tranh chap.

## 6.9. Settle contract khi khong tranh chap

API:
- `POST /api/contracts/{contract_id}/settle`

Flow nay dung khi contract khong di vao nhanh tranh chap.

Xu ly:
1. tinh `tongTienThanhToan`
2. tach thanh:
- `gross`
- `platform fee = 10%`
- `owner net = gross - fee`
3. tao cac tx:
- `SETTLE_PAYMENT`
- `RENTAL_PAYMENT_GROSS`
- `PLATFORM_FEE_CHARGED`
- `OWNER_NET_PAYOUT`
4. neu co hoan coc thi tao them:
- `REFUND_DEPOSIT`
- `ESCROW_REFUND`
5. mine block local va mirror sang Supabase

Quan trong:
- Tren cung 1 contract, ban chi di theo 1 nhanh ket thuc chinh:
  - hoac `settle`
  - hoac `damage claim -> admin confirm`
- Sau khi contract da hoan thanh, goi `settle` lai se bi tu choi.

## 7. Mirror, reconcile va idempotency

### Mirror block
Moi block sau khi mine se duoc mirror xuong cac bang:
- `Block`
- `Transaction`
- `Event`

Mirror da duoc lam theo huong idempotent:
- block tranh duplicate theo `hash`
- transaction tranh duplicate theo `txHash`
- event tranh duplicate theo `eventId`

### Reconcile
API:
- `GET /api/node/reconcile`
- `POST /api/node/reconcile`

Dung khi local chain va Supabase lech nhau. Backend se doc toan bo `NodeData` va mirror lai nhung block chua co tren DB.

### Align local head voi DB
Truoc khi mine block moi, backend se:
1. doc latest block trong Supabase
2. so sanh voi local head trong `NodeData`
3. neu DB dang di truoc thi dong bo local head

Muc tieu la tranh loi duplicate `blockHeight` khi restart server hoac test nhieu vong.

## 8. Cac endpoint quan trong

### Auth
- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/wallet/nonce`
- `POST /auth/wallet/verify`
- `POST /auth/wallet/unlink`

### Nghiep vu
- `POST /api/vehicles`
- `POST /api/bookings`
- `POST /api/contracts/create`
- `POST /api/contracts/{contract_id}/lock-deposit`
- `POST /api/contracts/{contract_id}/return-vehicle`
- `POST /api/contracts/{contract_id}/damage-claim`
- `POST /api/disputes/{dispute_id}/admin-confirm-no-damage`
- `POST /api/disputes/{dispute_id}/admin-confirm-damage`
- `POST /api/contracts/{contract_id}/settle`

### Chain va finance
- `GET /api/overview`
- `GET /api/node/chain`
- `GET /api/wallets/overview`
- `GET /api/finance/summary`
- `GET /api/finance/transactions`
- `GET /api/contracts/{contract_id}/money-flow`
- `GET /api/node/reconcile`
- `POST /api/node/reconcile`

## 9. Frontend de test

Sau khi chay backend, co the mo:

- `http://127.0.0.1:8000/frontend/auth.html`
- `http://127.0.0.1:8000/frontend/owner.html`
- `http://127.0.0.1:8000/frontend/renter.html`
- `http://127.0.0.1:8000/frontend/admin.html`
- `http://127.0.0.1:8000/frontend/finance.html`
- `http://127.0.0.1:8000/frontend/index.html`

Cac trang frontend hien co:
- nav loc theo role `admin / chuXe / khach`
- thong tin tai khoan dang dang nhap
- danh sach vi va so du lien quan
- activity log va JSON log
- du lieu tham chieu de copy nhanh `bookingId`, `contractId`, `disputeId`

## 10. Cach chay backend

```bash
cd backend2
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

## 11. Flow test de nghi

## Nhanh 1: flow thue xe khong tranh chap
1. seed balance cho wallet renter trong Supabase
2. login `chuXe`
3. them xe
4. logout, login `khach`
5. tao booking
6. tao contract
7. lock deposit
8. settle contract
9. login `admin`
10. mo `finance.html` de kiem tra:
- owner net payout
- platform fee
- refund neu co

## Nhanh 2: flow tranh chap co hu hai
1. seed balance cho renter
2. `chuXe` them xe
3. `khach` tao booking
4. tao contract
5. lock deposit
6. return vehicle
7. `chuXe` tao damage claim
8. `admin` confirm damage
9. kiem tra `money-flow` cua contract va `finance summary`

## Nhanh 3: flow tranh chap khong hu hai
1. lock deposit
2. return vehicle
3. owner damage claim
4. admin confirm no damage
5. kiem tra renter duoc refund toan bo deposit
6. fee wallet khong tang

## 12. Ghi chu quan trong khi demo

- `adminId` la `NguoiDung.id` cua user co `vaiTro = 'admin'`
- `disputeId` khac `contractId`; khi admin confirm phai dung dung `disputeId`
- `approvedCost` trong `admin-confirm-damage` khong duoc vuot qua deposit dang khoa
- `damage claim` chi hop le sau khi `return vehicle`
- sau khi contract da di vao nhanh `admin confirm`, khong the `settle` lai tren cung contract do

## 13. Vi du thong diep log thuc te

Terminal backend se in log de de theo doi demo, vi du:

```text
[SERVICE] ... action=lock_deposit_success contractId=cb3d9721-a55f-4620-9a9d-e6cc3b3583de txHash=TX73E2A8B08152 blockHeight=16 amount=2000000.0
[SERVICE] ... action=damage_claim_success contractId=cb3d9721-a55f-4620-9a9d-e6cc3b3583de disputeId=5a6e6914-ccfd-4b4b-b40b-ee3142058f0b reportId=f44fd8f5-88b9-4429-8cda-e209931f881c txHash=TX3549DCA975C2
[SERVICE] ... action=admin_confirm_damage_success disputeId=5a6e6914-ccfd-4b4b-b40b-ee3142058f0b blockHeight=19 gross=2000000.0 fee=200000.0 net=1800000.0 refund=0.0
```

Cac log nay khop voi cac block JSON trong `backend2/NodeData/Blocks` nen rat thuan tien de demo va doi chieu.
