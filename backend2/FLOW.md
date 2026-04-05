# Backend2 Flow

## Tong quan

`backend2` la backend hybrid cho he thong thue xe:

- Blockchain local nam trong `NodeData`
- Supabase luu du lieu nghiep vu va du lieu query/report
- Cac buoc tai chinh va phap ly quan trong se tao local transaction, mine block local, roi mirror sang Supabase

## Thanh phan chinh

- `backend2/server.py`: khai bao FastAPI app, route auth, route nghiep vu, mount `/frontend`
- `backend2/modules/auth.py`: dang ky, dang nhap, session token, lien ket MetaMask
- `backend2/modules/service.py`: logic thue xe, hop dong, tien coc, tranh chap, mirror blockchain
- `backend2/modules/node_storage.py`: quan ly local chain trong `NodeData`
- `frontend/`: cac trang test flow bang HTML/JS thuan

## Mo hinh hybrid

He thong su dung 2 lop du lieu song song:

1. Local blockchain
- Tao transaction local cho cac buoc quan trong
- Mine block local
- Luu block/tx vao `NodeData`
- Day la lop du lieu bat bien, phuc vu audit

2. Supabase
- Luu du lieu nghiep vu: user, wallet, xe, booking, contract, deposit, dispute
- Luu block, transaction, event de query/report
- Frontend chu yeu doc overview tu day

## Flow auth

### 1. Dang ky

API: `POST /auth/register`

- Nhan `hoTen`, `email` hoac `soDienThoai`, `password`
- Kiem tra trung email/so dien thoai
- Hash password vao `mkHash`
- Tao user trong bang `NguoiDung`
- In log auth ra terminal

### 2. Dang nhap

API: `POST /auth/login`

- Login bang `email` hoac `soDienThoai`
- Kiem tra `mkHash`
- Chi cho dang nhap neu `trangThai = hoatDong`
- Cap nhat `lanDangNhapCuoi`
- Tao JWT token
- Tao session trong `AuthSession`
- In log auth ra terminal

### 3. Xem user hien tai

API: `GET /auth/me`

- Doc token Bearer
- Xac thuc JWT
- Kiem tra session trong `AuthSession`
- Tra user hien tai va danh sach wallet lien ket

### 4. Dang xuat

API: `POST /auth/logout`

- Doc token
- Revoke session trong `AuthSession`
- In log auth ra terminal

### 5. Lien ket MetaMask

Buoc 1: `POST /auth/wallet/nonce`
- Backend tao challenge va SIWE-style message
- Luu challenge vao `WalletAuthChallenge`

Buoc 2: Frontend goi MetaMask `personal_sign`
- Ky message off-chain

Buoc 3: `POST /auth/wallet/verify`
- Backend recover address tu chu ky
- So sanh voi wallet address gui len
- Neu hop le thi insert/update vao bang `Wallet`
- Danh dau challenge da dung
- In log auth ra terminal

## Flow nghiep vu chinh

### 1. Owner them xe

API: `POST /api/vehicles`

- Tim owner theo email
- Tao ban ghi xe trong bang `Xe`
- Chua mine block

### 2. Renter tao booking

API: `POST /api/bookings`

- Tim renter theo token dang nhap
- Kiem tra renter co role `khach` va `trangThai = hoatDong`
- Tim xe theo `xeId`
- Kiem tra xe dang `sanSang` va khong co booking / contract active trung xe
- Tinh `soNgayThue`, `tongTienThue`
- Snapshot `diemUyTinLucDat = diemDanhGiaTb` tai thoi diem dat
- Xac dinh che do tu dong:
  - Neu `diemUyTinLucDat >= 90`:
    - `cheDoTuDong = autoApprove15m`
    - `hanDuyetLuc = now + 15 phut`
  - Neu `diemUyTinLucDat < 90`:
    - `cheDoTuDong = autoCancel60m`
    - `hanDuyetLuc = now + 60 phut`
- Tao ban ghi `DangKy`
- Dat `trangThai = choXacNhan`
- Chua tao `HopDongThue`
- Chua tao `TienCoc`
- Chua mine block

### 3. Owner xem booking cho duyet

API: `GET /api/owner/bookings`

- Chi owner cua xe hoac admin duoc xem
- Tra danh sach booking cua cac xe owner so huu
- Hydrate them thong tin xe, thong tin renter, `remainingSeconds`, `expired`, `ownerActionAllowed`
- Frontend owner dung endpoint nay de hien thi countdown va mode auto

### 4. Owner duyet booking thu cong

API: `POST /api/bookings/{booking_id}/approve`

- Chi owner cua xe hoac admin duoc duyet
- Neu booking da qua `hanDuyetLuc` ma chua resolve, backend resolve truoc de tranh race condition
- Chi cho duyet khi booking dang `choXacNhan`
- Cap nhat booking:
  - `trangThai = daDuyet`
  - `quyetDinhBoi = chuXe` hoac `admin`
  - `nguoiRaQuyetDinhId = actor_user_id`
  - `quyetDinhLuc = now`
  - `ghiChuHeThong = Duyet thu cong`
- Sau do moi tao `HopDongThue` va `TienCoc`
- Cap nhat booking thanh `daTaoHopDong`
- Chua mine block o buoc nay

### 5. Owner tu choi booking thu cong

API: `POST /api/bookings/{booking_id}/reject`

- Chi owner cua xe hoac admin duoc tu choi
- Neu booking da qua `hanDuyetLuc` ma chua resolve, backend resolve truoc
- Chi cho tu choi khi booking dang `choXacNhan`
- Cap nhat booking:
  - `trangThai = daHuy`
  - `lyDoHuy = ly do owner nhap`
  - `quyetDinhBoi = chuXe` hoac `admin`
  - `nguoiRaQuyetDinhId = actor_user_id`
  - `quyetDinhLuc = now`
  - `ghiChuHeThong = Tu choi thu cong`
- Khong tao contract
- Khong tao deposit
- Chua mine block

### 6. Auto resolve booking het han

API noi bo: `POST /api/internal/jobs/resolve-expired-bookings`

- Duoc goi boi cron / Task Scheduler, bao ve bang header `X-Internal-Job-Secret`
- Quet booking co:
  - `trangThai = choXacNhan`
  - `hanDuyetLuc <= now()`
- Xu ly idempotent, co the goi lap lai nhieu lan

Rule auto resolve:
- Neu `cheDoTuDong = autoApprove15m`
  - Auto duyet booking
  - Set `quyetDinhBoi = heThong`
  - Set `quyetDinhLuc = now`
  - Set `ghiChuHeThong = Auto duyet do diem uy tin >= 90 va chu xe khong phan hoi trong 15 phut`
  - Tao `HopDongThue` + `TienCoc` dung 1 lan
  - Booking cuoi cung = `daTaoHopDong`
- Neu `cheDoTuDong = autoCancel60m`
  - Auto huy booking
  - Set `trangThai = daHuy`
  - Set `lyDoHuy = Qua 60 phut chu xe khong duyet`
  - Set `quyetDinhBoi = heThong`
  - Set `quyetDinhLuc = now`
  - Set `ghiChuHeThong = Auto huy do diem uy tin < 90 va chu xe khong phan hoi trong 60 phut`
  - Khong tao contract
  - Khong tao deposit

Luu y:
- Neu owner da duyet truoc han thi auto job se skip
- Neu owner da tu choi truoc han thi auto job se skip
- Neu booking da co contract roi thi job khong tao lai, chi dong bo trang thai neu can
- Chua mine block o buoc nay

### 7. Khoa tien coc

API: `POST /api/contracts/{contract_id}/lock-deposit`

Dieu kien:
- Contract dang o trang thai khoi tao
- Deposit dang `chuaKhoa`

Xu ly:
- Tao tx `LOCK_DEPOSIT`
- `fromAddress` = wallet renter
- `toAddress` = `SYSTEM_ESCROW_ADDRESS`
- Mine block local
- Mirror block/tx/event sang Supabase
- Cap nhat `TienCoc.trangThai = daKhoa`
- Cap nhat `HopDongThue.trangThai = dangThue`

### 8. Khach tra xe

API: `POST /api/contracts/{contract_id}/return-vehicle`

Dieu kien:
- Contract dang thue
- Deposit da khoa
- Nguoi tra phai la nguoi thue cua contract

Xu ly:
- Tao `evidenceHash`
- Tao tx `VEHICLE_RETURNED`
- Mine block local
- Mirror sang Supabase
- Danh dau contract da nhan lai xe
- Luu hash vao `summaryHash`

### 9. Owner khiu nai hu hai

API: `POST /api/contracts/{contract_id}/damage-claim`

Dieu kien:
- Xe da duoc tra
- Owner dung voi contract
- Deposit dang khoa
- Chua co dispute mo cho contract

Xu ly:
- Tao `BaoCaoHuHai`
- Tao `TranhChap`
- Tao tx `DAMAGE_CLAIMED`
- Mine block local
- Mirror sang Supabase
- Tam giu deposit de tranh chap

### 10. Admin xac nhan khong hu hai

API: `POST /api/disputes/{dispute_id}/admin-confirm-no-damage`

Dieu kien:
- Dispute dang cho admin xu ly
- Admin phai co role admin
- Admin phai co wallet

Xu ly:
- Tao tx `ADMIN_DECISION_NO_DAMAGE`
- Tao tx `REFUND_DEPOSIT`
- Mine block local
- Mirror sang Supabase
- Dong dispute voi ket qua `khongCoHuHai`
- Hoan toan bo deposit cho renter
- Danh dau contract hoan thanh

### 11. Admin xac nhan co hu hai

API: `POST /api/disputes/{dispute_id}/admin-confirm-damage`

Dieu kien:
- Dispute dang cho admin xu ly
- `approvedCost` khong duoc vuot qua tien coc dang khoa

Xu ly:
- Tao tx `ADMIN_DECISION_DAMAGE_CONFIRMED`
- Tao tx `PAYOUT_DEPOSIT_TO_OWNER`
- Neu con du tien coc thi tao them `REFUND_DEPOSIT`
- Mine block local
- Mirror sang Supabase
- Dong dispute voi ket qua `coHuHai`
- Chuyen mot phan hoac toan bo tien coc cho owner
- Hoan phan du cho renter neu co
- Danh dau contract hoan thanh

### 12. Tat toan contract theo flow cu

API: `POST /api/contracts/{contract_id}/settle`

- Dung cho truong hop khong co tranh chap
- Tao tx `SETTLE_PAYMENT`
- Neu co hoan coc thi tao `REFUND_DEPOSIT`
- Mine block local
- Mirror sang Supabase
- Cap nhat contract va deposit thanh hoan tat

## Flow blockchain local

Moi buoc tai chinh/phap ly quan trong deu theo chu trinh:

1. Tao transaction bang `make_tx`
2. Mine block bang `mine_block`
3. Ghi vao `NodeData`
4. Mirror sang Supabase bang `mirror_block`

## Mirror va reconcile

### Mirror

`mirror_block()` se:
- Ghi block vao bang `Block`
- Ghi tx vao bang `Transaction`
- Ghi event vao bang `Event`
- Co co che tranh duplicate theo `hash`, `txHash`, `eventId`

### Reconcile

API: `POST /api/node/reconcile`

- Doc chain local trong `NodeData`
- Mirror lai cac block/tx chua co tren DB
- Dung khi local chain va Supabase bi lech

### Align local head voi DB

Truoc khi mine block moi:
- Backend doc latest block trong DB
- So voi local head trong `NodeData`
- Neu DB dang di truoc thi dong bo local head theo DB
- Muc tieu la tranh loi duplicate `blockHeight`

## Overview va frontend

### Overview

API: `GET /api/overview`

- Tra du lieu tong hop tu Supabase
- Tra them metadata cua local chain tu `NodeData`
- Neu phan DB loi, backend van uu tien tra duoc phan local chain theo huong hybrid

### Frontend test

- `/frontend/index.html`: full console cho toan bo flow
- `/frontend/owner.html`: cac thao tac owner
- `/frontend/renter.html`: cac thao tac renter
- `/frontend/auth.html`: register/login/link wallet

Tat ca trang frontend deu co:
- Nut utility `Load Overview`, `Load Chain`, `Run Reconcile`
- Khung `Du Lieu Tham Chieu` de copy nhanh user, vehicle, booking, contract, dispute
- Khung `JSON Log` de xem response API

## Bang du lieu chinh

- `NguoiDung`
- `Wallet`
- `Xe`
- `DangKy`
- `HopDongThue`
- `TienCoc`
- `BaoCaoHuHai`
- `TranhChap`
- `Block`
- `Transaction`
- `Event`
- `AuthSession`
- `WalletAuthChallenge`

## Ghi chu ve trang thai

Schema DB goc cua du an khong co day du tat ca trang thai nghiep vu mo rong nhu:
- `choKiemTraTraXe`
- `dangTranhChap`
- `tamGiuDoTranhChap`

Vi vay backend2 dang xu ly theo cach:
- Logic ung dung van hieu cac trang thai mo rong nay
- Khi ghi xuong DB, se map ve gia tri hop le theo schema hien tai
- Metadata chi tiet van duoc luu trong blockchain local va `rawData` cua transaction/event

## Flow test de nghi

1. Dang ky 2 user: owner va renter
2. Dang nhap owner, lien ket wallet
3. Dang nhap renter, lien ket wallet
4. Owner them xe
5. Renter tao booking
6. Owner vao danh sach booking cho duyet
7. Chon 1 trong 3 nhanh:
- Owner duyet thu cong
- Owner tu choi thu cong
- De job auto resolve xu ly sau khi het han
8. Neu booking duoc duyet thi hop dong va tien coc moi duoc tao
9. Lock deposit
10. Renter return vehicle
11. Owner tao damage claim
12. Admin confirm no damage hoac confirm damage
13. Kiem tra `overview`, `chain`, `block`, `transaction`, `event`


