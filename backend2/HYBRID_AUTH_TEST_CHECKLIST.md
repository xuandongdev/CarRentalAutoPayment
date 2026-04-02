# Hybrid Auth Test Checklist

Tai lieu nay test dung 9 case bat buoc cho Hybrid Auth (password + wallet + step-up).

## Dieu kien truoc khi test
- Backend dang chay: `python server.py` trong thu muc `backend2`.
- Frontend dang truy cap duoc `/login`.
- Co it nhat 3 user test trong DB:
  - `khach` hoat dong
  - `chuXe` hoat dong
  - `admin` hoat dong
- Co it nhat 1 user da lien ket wallet active.
- Co it nhat 1 user bi `tamKhoa` hoac `ngungHoatDong`.

## CASE 1 - Password login thanh cong
1. Vao `/login`, tab `Tai khoan`.
2. Nhap email/sdt + password dung.
3. Bam `Dang nhap`.

Expected:
- API `POST /auth/login` tra `accessToken`.
- Co row moi trong `AuthSession`.
- Redirect dung role:
  - `khach` -> `/renter/dashboard`
  - `chuXe` -> `/owner/dashboard`
  - `admin` -> `/admin/dashboard`

## CASE 2 - Password login that bai
1. Nhap identifier dung nhung password sai.
2. Bam `Dang nhap`.

Expected:
- API tra loi auth (`Thong tin dang nhap khong hop le`).
- Khong tao them `AuthSession`.
- UI hien thong bao loi ro rang.

## CASE 3 - User bi khoa
1. Dung account co `trangThai = tamKhoa` hoac `ngungHoatDong`.
2. Thu login bang password.

Expected:
- Login bi chan.
- Khong tao `AuthSession`.
- UI hien dung thong diep trang thai bi chan.

## CASE 4 - Wallet login thanh cong
1. Vao `/login`, tab `Vi MetaMask`.
2. Bam `Ket noi MetaMask`.
3. Bam `Ky de dang nhap`.

Expected:
- API challenge: `POST /auth/wallet/challenge` voi `purpose=login_wallet` thanh cong.
- MetaMask mo popup ky `personal_sign`.
- API verify: `POST /auth/wallet/verify` thanh cong, tra `accessToken`.
- Tao `AuthSession` moi.
- Redirect dung dashboard theo role.

## CASE 5 - Wallet chua lien ket
1. Dung 1 vi chua lien ket user nao.
2. Thu wallet login.

Expected:
- Challenge bi tu choi voi business error: vi chua lien ket.
- Khong tao session.
- UI goi y dang nhap tai khoan de lien ket vi.

## CASE 6 - Challenge het han hoac da dung
1. Tao challenge wallet.
2. Dung challenge da verify roi hoac de qua han.
3. Goi verify lai.

Expected:
- Verify that bai (`Challenge da duoc su dung` hoac `Challenge da het han`).
- Khong tao session moi.

## CASE 7 - Signature sai
1. Tao challenge hop le.
2. Gui signature khong khop message/address.

Expected:
- Verify that bai (`Chu ky khong khop voi walletAddress`).
- Khong tao session.

## CASE 8 - Step-up auth
1. Dang login binh thuong.
2. Thu thao tac nhay cam (lock coc, tra xe, damage claim, settle, admin dispute).
3. He thong yeu cau ky vi step-up.

Expected:
- Frontend goi:
  - `POST /auth/wallet/step-up/challenge`
  - `POST /auth/wallet/step-up/verify`
- API nghiep vu gui kem header `X-Step-Up-Challenge-Id`.
- Neu khong co header hoac challenge het hieu luc -> bi chan.

## CASE 9 - Redirect sau login theo role
- Xac nhan login password va wallet deu redirect dung:
  - `khach` -> `/renter/dashboard`
  - `chuXe` -> `/owner/dashboard`
  - `admin` -> `/admin/dashboard`

## Ghi chu bao mat
- Khong bao gio nhap private key/seed phrase vao he thong.
- Wallet login chi dung `connect + sign challenge`, khong gui transaction.
