# FLOW HỆ THỐNG (server_test)

Tài liệu này mô tả vai trò từng file và luồng xử lý nghiệp vụ thuê xe theo đúng code hiện tại.




---

## 1) Vai trò từng file

### `Server.py`
File chạy chính, điều phối toàn bộ demo:
- Khởi tạo blockchain và service
- Tạo tài khoản renter/owner
- Tạo hợp đồng
- Khóa cọc, ghi nhận usage, tất toán
- Mine block cho các giao dịch pending
- Xuất chain ra JSON

### `Service/RentalService.py`
Lớp nghiệp vụ thuê xe:
- Tạo `RentalContract`
- Tạo `Transaction` cho các bước `DEPOSIT_LOCK`, `RENTAL_PAYMENT`, `DEPOSIT_REFUND`
- Đẩy giao dịch sang `Blockchain`

### `Blockchain.py`
Lõi blockchain, quản lý state:
- `accounts`, `contracts`, `pendingTransactions`, `chain`
- Tạo genesis block
- Validate và nhận transaction
- Mine block từ pending transactions
- Áp dụng transaction để cập nhật account + contract
- Kiểm tra tính hợp lệ chain
- Export JSON

### `Block.py`
Mô hình block:
- Chứa danh sách transaction
- Tính `merkleRoot`
- Tính `blockHash`

### `Transaction.py`
Mô hình giao dịch:
- Dữ liệu giao dịch và metadata
- Dữ liệu để ký
- Ký giao dịch
- Tính `txHash`

### `Account.py`
Mô hình tài khoản (`AccountState`):
- Quản lý số dư khả dụng
- Quản lý số dư khóa (`lockedBalance`)
- `credit`, `debit`, `lock_funds`, `unlock_funds`, `consume_locked_funds`

### `RentalContract.py`
Mô hình hợp đồng thuê:
- Thông tin booking/vehicle/renter/owner
- Tiền cọc, trạng thái hợp đồng
- `usageSummary`, phí phát sinh, tổng tiền thanh toán, hoàn cọc

### `Service/HashService.py`
Tiện ích hash dùng chung:
- `sha256_text`, `sha256_obj`
- `calc_merkle_root`
- `now_iso`

---

## 2) Flow nghiệp vụ chuẩn

### Bước 0: Khởi tạo
1. `Server.py` tạo `Blockchain`
2. `Blockchain` tự tạo genesis block
3. `Server.py` tạo `RentalService(blockchain)`

### Bước 1: Tạo tài khoản
1. Nhập thông tin renter và owner (`ownerName`, `balance`, `secret`)
2. Hệ thống tự hash để tạo `address` ví
3. Tạo 2 object `AccountState`
4. Gọi `blockchain.register_account(...)`

### Bước 2: Tạo hợp đồng
1. Nhập thông tin hợp đồng (`contractId`, `bookingId`, `vehicleId`, `depositAmount`)
2. Gọi `RentalService.create_contract(...)`
3. Contract được lưu vào `blockchain.contracts`

### Bước 3: Khóa cọc
1. Gọi `RentalService.lock_deposit(contractId, renter_secret)`
2. Tạo transaction `DEPOSIT_LOCK` và ký
3. Giao dịch được thêm vào `blockchain.pendingTransactions`
4. Khi mine:
   - Tạo block mới
   - Apply transaction: trừ balance renter, tăng `lockedBalance`, cập nhật contract `lockedDeposit` + status
   - Đánh dấu tx `CONFIRMED`

### Bước 4: Ghi nhận usage
1. Nhập thông tin sử dụng xe
2. Gọi `RentalService.record_usage(...)`
3. Contract cập nhật `usageSummary` và `usageSummaryHash`

### Bước 5: Tất toán hợp đồng
1. Gọi `RentalService.settle_contract(...)`
2. Service tạo `RENTAL_PAYMENT`
3. Nếu có hoàn cọc, tạo thêm `DEPOSIT_REFUND`
4. Đưa các tx vào pending
5. Khi mine:
   - Apply `RENTAL_PAYMENT`: chuyển tiền cho owner (ưu tiên dùng lockedBalance của renter)
   - Apply `DEPOSIT_REFUND`: hoàn phần dư cọc về renter
   - Contract chuyển trạng thái hoàn tất

### Bước 6: Xuất dữ liệu
1. Gọi `blockchain.export_to_json("data/chain.json")`
2. Ghi toàn bộ chain + state hiện tại ra file JSON

---

## 3) Tóm tắt ngắn

`Server.py` điều phối flow, `Service/RentalService.py` xử lý nghiệp vụ thuê xe, `Blockchain.py` xác thực + ghi nhận giao dịch thành block, các model (`Account`, `Transaction`, `Block`, `RentalContract`) giữ dữ liệu, và `Service/HashService.py` cung cấp hàm hash/timestamp dùng chung.

---

## 4) Chain mẫu (kết quả chạy thực tế)

```json
{
   "chainId": "carRentalAutoPayment",
   "isValid": true,
   "accounts": [
      {
         "address": "0x33C5B0A091F94857",
         "ownerName": "xuan dong",
         "role": "RENTER",
         "balance": 69000.0,
         "lockedBalance": 0.0,
         "nonce": 0,
         "publicKey": null,
         "status": "ACTIVE",
         "createdAt": "2026-03-19T11:24:35.830842+00:00",
         "updatedAt": "2026-03-19T11:25:51.226809+00:00"
      },
      {
         "address": "0x4A199F6999AD7AF8",
         "ownerName": "huu dan",
         "role": "OWNER",
         "balance": 231000.0,
         "lockedBalance": 0.0,
         "nonce": 0,
         "publicKey": null,
         "status": "ACTIVE",
         "createdAt": "2026-03-19T11:24:43.762833+00:00",
         "updatedAt": "2026-03-19T11:25:51.226809+00:00"
      }
   ],
   "contracts": [
      {
         "contractId": "thue01",
         "bookingId": "thuexe01",
         "vehicleId": "xe01",
         "renterAddress": "0x33C5B0A091F94857",
         "ownerAddress": "0x4A199F6999AD7AF8",
         "depositAmount": 50000.0,
         "lockedDeposit": 31000.0,
         "startTime": null,
         "endTime": null,
         "actualPickupTime": null,
         "actualReturnTime": null,
         "usageSummary": {
            "totalKm": 10.0,
            "totalHours": 1.0,
            "lateMinutes": 0,
            "fuelPercent": 70.0,
            "note": ""
         },
         "usageSummaryHash": "41696a82ce018e0e7442cbad369e92b8a01d79c34236ed0ff4d7e0397dbedfdc",
         "overtimeFee": 5000.0,
         "fuelFee": 1000.0,
         "damageFee": 5000.0,
         "penaltyTotal": 11000.0,
         "finalCharge": 31000.0,
         "refundAmount": 19000.0,
         "contractStatus": "COMPLETED",
         "createdAt": "2026-03-19T11:25:09.157301+00:00",
         "updatedAt": "2026-03-19T11:25:51.226809+00:00"
      }
   ],
   "pendingTransactions": [],
   "chain": [
      {
         "blockNumber": 0,
         "previousHash": "0000000000000000000000000000000000000000000000000000000000000000",
         "timestamp": "2026-03-19T11:24:24.112852+00:00",
         "validatorAddress": "SYSTEM",
         "merkleRoot": "b455de01b61e6f9e8d254bf14d5f2f0146bd51b6dd39ccc6b33354eabec138a1",
         "blockHash": "99d8e8bb58580b17c2cbb69b07cf5c7770a1abb1aedc97ec6a753327e415cd99",
         "transactions": [
            {
               "txHash": "85617145408a0d8d79be0c726161ded6d7048f536da1548509d57969f67f0fc1",
               "txType": "GENESIS",
               "fromAddress": "SYSTEM",
               "toAddress": null,
               "amount": 0,
               "contractId": null,
               "metadata": {
                  "message": "Genesis Block"
               },
               "timestamp": "2026-03-19T11:24:24.112852+00:00",
               "signature": "GENESIS_SIGNATURE",
               "status": "CONFIRMED",
               "blockNumber": 0,
               "blockHash": "99d8e8bb58580b17c2cbb69b07cf5c7770a1abb1aedc97ec6a753327e415cd99",
               "txIndex": 0
            }
         ]
      },
      {
         "blockNumber": 1,
         "previousHash": "99d8e8bb58580b17c2cbb69b07cf5c7770a1abb1aedc97ec6a753327e415cd99",
         "timestamp": "2026-03-19T11:25:15.109594+00:00",
         "validatorAddress": "0xVALIDATOR001",
         "merkleRoot": "f7cbe4a31e6fd6caccc522bd1ae02ecdb48211439105905d9e14ee88a443e643",
         "blockHash": "d7536ec9d39635d4f5e949dc55693aa737d1e0180ee1ed192ee1cb5ee6108911",
         "transactions": [
            {
               "txHash": "99822b8031f7c1e99f5c2550147a149aa750a1a2e8c6c751152b7a6f85a90478",
               "txType": "DEPOSIT_LOCK",
               "fromAddress": "0x33C5B0A091F94857",
               "toAddress": "SYSTEM_ESCROW",
               "amount": 50000.0,
               "contractId": "thue01",
               "metadata": {
                  "action": "lockDeposit",
                  "vehicleId": "xe01",
                  "bookingId": "thuexe01"
               },
               "timestamp": "2026-03-19T11:25:11.708379+00:00",
               "signature": "3031356a7ecd74b657ed1af3bb046b74fd7c5028cd7dc8dc5c63498f579a75af",
               "status": "CONFIRMED",
               "blockNumber": 1,
               "blockHash": "d7536ec9d39635d4f5e949dc55693aa737d1e0180ee1ed192ee1cb5ee6108911",
               "txIndex": 0
            }
         ]
      },
      {
         "blockNumber": 2,
         "previousHash": "d7536ec9d39635d4f5e949dc55693aa737d1e0180ee1ed192ee1cb5ee6108911",
         "timestamp": "2026-03-19T11:25:51.226809+00:00",
         "validatorAddress": "0xVALIDATOR001",
         "merkleRoot": "c76b6f34cf588ee5f8213b159bbde75de12bb26f8265582753231923b9140c21",
         "blockHash": "dc9af446c7f8ed10b122b0475d03b45ced1763672335690a57d0ecf5be788da7",
         "transactions": [
            {
               "txHash": "4506575b492378837751dbc539d5f708b002826946df7d6556fe1ccaa80ba810",
               "txType": "RENTAL_PAYMENT",
               "fromAddress": "0x33C5B0A091F94857",
               "toAddress": "0x4A199F6999AD7AF8",
               "amount": 31000.0,
               "contractId": "thue01",
               "metadata": {
                  "action": "settlePayment",
                  "usageSummaryHash": "41696a82ce018e0e7442cbad369e92b8a01d79c34236ed0ff4d7e0397dbedfdc"
               },
               "timestamp": "2026-03-19T11:25:49.550237+00:00",
               "signature": "9a205bb131e00fad8cd9e5cb8ddae9f9dfc267365fa95aba58b59e62f6b65523",
               "status": "CONFIRMED",
               "blockNumber": 2,
               "blockHash": "dc9af446c7f8ed10b122b0475d03b45ced1763672335690a57d0ecf5be788da7",
               "txIndex": 0
            },
            {
               "txHash": "3f29426a17106ccc71c5dff3eff91677c31b540f3dacf6e21380ed585ec011ae",
               "txType": "DEPOSIT_REFUND",
               "fromAddress": "SYSTEM_ESCROW",
               "toAddress": "0x33C5B0A091F94857",
               "amount": 19000.0,
               "contractId": "thue01",
               "metadata": {
                  "action": "refundDeposit"
               },
               "timestamp": "2026-03-19T11:25:49.550237+00:00",
               "signature": "843981ba201018dd23815e37f1b87be732db942e736031bd8c9ef53b3f97b80e",
               "status": "CONFIRMED",
               "blockNumber": 2,
               "blockHash": "dc9af446c7f8ed10b122b0475d03b45ced1763672335690a57d0ecf5be788da7",
               "txIndex": 1
            }
         ]
      }
   ]
}
```


cd "d:\6. Blockchain\blockchain_code\code\CarRentalAutoPayment\backend2"
.\.venv\Scripts\Activate.ps1

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

python server.py