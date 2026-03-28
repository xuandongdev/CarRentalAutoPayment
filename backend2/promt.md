Bạn đang làm việc trên repo CarRentalAutoPayment, branch hiện tại là xuandongdev.

Mục tiêu:
Mở rộng backend hybrid hiện có để hỗ trợ đầy đủ flow tranh chấp tiền cọc:
khách trả xe -> owner khiếu nại hư hại -> admin kiểm chứng -> admin xác nhận KHÔNG hư hại -> hệ thống hoàn toàn bộ tiền cọc cho khách.
Đồng thời hỗ trợ luôn nhánh ngược lại:
admin xác nhận CÓ hư hại -> hệ thống chuyển một phần hoặc toàn bộ tiền cọc cho owner, phần dư hoàn lại cho khách nếu có.

Yêu cầu rất quan trọng:
- Không phá vỡ flow hiện có: tạo booking, tạo contract, lock deposit, settle contract.
- Ưu tiên chỉnh trực tiếp trong backend/server.py nếu cấu trúc hiện tại đang tập trung logic ở đó.
- Nếu cần, tách thêm helper/service nhỏ nhưng không được làm thay đổi kiến trúc quá mạnh.
- Giữ mô hình hybrid:
  - blockchain local trong NodeData là nơi lưu block/tx bất biến
  - Supabase là nơi lưu dữ liệu nghiệp vụ và dữ liệu query/report
- Mọi bước tài chính hoặc pháp lý quan trọng phải sinh transaction local, mine block local, rồi mirror sang Supabase qua cơ chế hiện có.
- Chỉ dùng logic tương thích với codebase hiện có. Không tự ý thay framework.

Việc cần làm:

1) Khảo sát nhanh code hiện tại rồi sửa đúng chỗ
- Tìm và dùng lại các thành phần đã có như:
  - LocalNodeStorage
  - RentalAppService
  - make_tx
  - mine_block
  - mirror_block
  - create_contract_from_booking
  - lock_deposit
  - settle_contract
- Không viết lại từ đầu nếu có thể mở rộng từ code cũ.

2) Thiết kế trạng thái nghiệp vụ rõ ràng
Bổ sung/chuẩn hóa trạng thái cho hợp đồng:
- khoiTao
- choKhoaCoc
- dangThue
- choKiemTraTraXe
- dangTranhChap
- adminXacNhanKhongHuHai
- adminXacNhanCoHuHai
- hoanThanh

Bổ sung/chuẩn hóa trạng thái cho tiền cọc:
- chuaKhoa
- daKhoa
- tamGiuDoTranhChap
- daHoan
- daChuyenChoOwner
- daTatToan

Bổ sung/chuẩn hóa trạng thái cho tranh chấp:
- moiTao
- choAdminXacMinh
- khongCoHuHai
- coHuHai
- daDong

Nếu codebase đang dùng tên trạng thái khác, hãy giữ backward compatibility ở mức hợp lý và ghi chú rõ trong code.

3) Thêm các transaction type blockchain mới
Bổ sung các tx_type sau:
- VEHICLE_RETURNED
- DAMAGE_CLAIMED
- ADMIN_DECISION_NO_DAMAGE
- ADMIN_DECISION_DAMAGE_CONFIRMED
- PAYOUT_DEPOSIT_TO_OWNER

Giữ lại các tx_type hiện có:
- LOCK_DEPOSIT
- SETTLE_PAYMENT
- REFUND_DEPOSIT

Mỗi transaction phải có:
- txHash
- txType
- fromAddress
- toAddress
- amount
- rawData
- signature/pseudo-signature theo cách codebase đang dùng
- timestamp nếu kiến trúc hiện tại hỗ trợ

4) Thêm flow trả xe
Tạo service method và API cho bước khách trả xe:
- POST /api/contracts/{contract_id}/return-vehicle

Request body đề xuất:
{
  "nguoiTraId": "...",
  "ghiChu": "Khach da tra xe",
  "evidenceUrls": ["..."],
  "evidenceMeta": {...}
}

Logic:
- Chỉ cho phép khi contract đang ở dangThue
- Tạo evidenceHash từ payload bằng cơ chế hash ổn định đang có trong repo
- Sinh transaction VEHICLE_RETURNED
- Mine block local
- mirror_block sang Supabase
- Cập nhật contract:
  - trangthai = choKiemTraTraXe
  - danhanlaixe = true hoặc cờ tương đương phù hợp ngữ cảnh
  - lưu returnEvidenceHash
  - lưu thoigiantraxe / capnhatluc nếu có cột phù hợp
- Trả về block + transaction + contract đã cập nhật

5) Thêm flow owner khiếu nại hư hại
Tạo service method và API:
- POST /api/contracts/{contract_id}/damage-claim

Request body đề xuất:
{
  "ownerId": "...",
  "lyDo": "Xe bi tray xuoc can sau",
  "estimatedCost": 1200000,
  "evidenceUrls": ["..."],
  "evidenceMeta": {...},
  "ghiChu": "Phat hien sau khi nhan lai xe"
}

Logic:
- Chỉ cho phép khi contract đang ở choKiemTraTraXe
- Tạo bản ghi baocaohuhai
- Tạo bản ghi tranhchap
- Tạo damageEvidenceHash
- Sinh transaction DAMAGE_CLAIMED
- Mine block local
- mirror_block sang Supabase
- Cập nhật:
  - contract.trangthai = dangTranhChap
  - deposit.trangthai = tamGiuDoTranhChap
  - dispute.trangthai = choAdminXacMinh
- Owner không được tự nhận tiền cọc
- Tiền cọc vẫn nằm ở SYSTEM_ESCROW_ADDRESS
- Trả về block + transaction + dispute + damage report

6) Thêm flow admin xác nhận KHÔNG hư hại
Tạo service method và API:
- POST /api/disputes/{dispute_id}/admin-confirm-no-damage

Request body đề xuất:
{
  "adminId": "...",
  "decisionNote": "Da doi chieu anh giao xe va anh tra xe, khong co hu hai moi",
  "evidenceMeta": {...}
}

Logic:
- Chỉ cho phép khi dispute đang ở choAdminXacMinh
- Sinh adminDecisionHash
- Tạo tx ADMIN_DECISION_NO_DAMAGE
- Tạo tx REFUND_DEPOSIT:
  - fromAddress = SYSTEM_ESCROW_ADDRESS
  - toAddress = contract.addressnguoithue
  - amount = full locked deposit hoặc đúng số tiền còn khóa
- Mine 1 block chứa cả 2 transaction hoặc 2 block riêng nếu kiến trúc hiện tại bắt buộc, nhưng ưu tiên 1 block cho cùng quyết định nghiệp vụ
- mirror_block sang Supabase
- Cập nhật:
  - dispute.trangthai = daDong
  - dispute.ketluan = khongCoHuHai
  - contract.trangthai = hoanThanh
  - deposit.trangthai = daHoan
  - deposit.sotienhoancoc = full deposit
  - deposit.txhashrefund = txHash REFUND_DEPOSIT
  - contract.tongtienhoanlai = full deposit nếu field này đang dùng theo flow hiện tại
- Trả về block + transactions + contract + deposit + dispute

7) Thêm flow admin xác nhận CÓ hư hại
Tạo service method và API:
- POST /api/disputes/{dispute_id}/admin-confirm-damage

Request body đề xuất:
{
  "adminId": "...",
  "approvedCost": 1000000,
  "decisionNote": "Xac nhan hu hai thuc te",
  "evidenceMeta": {...}
}

Logic:
- Chỉ cho phép khi dispute đang ở choAdminXacMinh
- approvedCost phải >= 0
- approvedCost không được vượt quá số tiền cọc đang khóa
- Sinh tx ADMIN_DECISION_DAMAGE_CONFIRMED
- Sinh tx PAYOUT_DEPOSIT_TO_OWNER:
  - fromAddress = SYSTEM_ESCROW_ADDRESS
  - toAddress = contract.addresschuxe
  - amount = approvedCost
- Nếu còn dư tiền cọc:
  - sinh tx REFUND_DEPOSIT cho phần còn lại về renter
- Mine block local
- mirror_block sang Supabase
- Cập nhật:
  - dispute.trangthai = daDong
  - dispute.ketluan = coHuHai
  - dispute.approvedcost = approvedCost
  - contract.trangthai = hoanThanh
  - deposit.trangthai = daChuyenChoOwner nếu approvedCost == full deposit, ngược lại là daTatToan hoặc trạng thái phù hợp nhất quán
  - deposit.sotienhoancoc = phần refund còn lại
- Trả về block + transactions + contract + deposit + dispute

8) Bổ sung request models Pydantic
Thêm các model request rõ ràng, dùng alias camelCase nếu file hiện tại đang theo kiểu đó:
- ReturnVehicleRequest
- CreateDamageClaimRequest
- AdminConfirmNoDamageRequest
- AdminConfirmDamageRequest

Mỗi model cần validate:
- chuỗi không rỗng khi bắt buộc
- estimatedCost / approvedCost >= 0
- evidenceUrls là list
- populate_by_name tương thích với phong cách hiện tại

9) Bổ sung helper nội bộ để tránh lặp logic
Tạo các helper private trong RentalAppService nếu cần:
- _build_evidence_hash(...)
- _mine_and_mirror(...)
- _ensure_contract_status(...)
- _ensure_dispute_status(...)
- _get_contract_and_deposit(...)
- _get_dispute_bundle(...)

Mục tiêu:
- Giảm lặp code
- Dễ đọc
- Không phá flow cũ

10) Bổ sung schema/migration nếu thiếu cột
Kiểm tra các bảng Supabase hiện dùng:
- hopdongthue
- tiencoc
- baocaohuhai
- tranhchap
- block
- transaction
- event

Nếu thiếu các cột phục vụ flow mới thì tạo file SQL migration mới, ví dụ:
- supabase/migrations/20260326_add_dispute_damage_flow.sql

Các cột có thể cần:
Trong hopdongthue:
- returnevidencehash
- txhashreturn
- blocknumberreturn
- txhashdecision
- decisionhash

Trong tiencoc:
- sotienchuyenchu xe (nếu muốn theo dõi rõ)
- txhashownerpayout

Trong baocaohuhai:
- hopdongthueid
- reporterid
- mota
- evidenceurls
- evidencehash
- estimatedcost
- createdat

Trong tranhchap:
- hopdongthueid
- baocaohuhaiid
- trangthai
- ketluan
- lydo
- estimatedcost
- approvedcost
- ownerclaimhash
- admindecisionhash
- txhashclaim
- txhashdecision
- createdat
- resolvedat

Nếu bảng đã có cột tương đương thì tái sử dụng, không thêm trùng.

11) Bổ sung event mirror nếu đang dùng bảng event
Khi mirror_block, đảm bảo các event mới được ghi đủ để overview/audit dễ đọc:
- vehicleReturned
- damageClaimed
- adminDecisionNoDamage
- adminDecisionDamageConfirmed
- payoutDepositToOwner
- refundDeposit

12) Mở rộng API overview
Cập nhật /api/overview để trả thêm tối thiểu:
- damageReports
- disputes
- nodeChain meta hoặc block mới nhất nếu đang có
- dữ liệu đủ để kiểm tra flow mới trên UI/demo

13) Bổ sung UI demo tối thiểu nếu trang HTML hiện tại đang là dashboard test
Nếu backend/server.py đang nhúng HTML_PAGE demo, hãy thêm form tối thiểu cho:
- trả xe
- owner khiếu nại hư hại
- admin xác nhận không hư hại
- admin xác nhận có hư hại

Yêu cầu UI:
- đơn giản
- không cần đẹp
- chỉ cần test được flow bằng nút bấm
- hiển thị kết quả JSON vào khung result/overview hiện có

14) Bổ sung xử lý lỗi rõ ràng
Phải trả HTTP 400 với detail dễ hiểu cho các case:
- contract sai trạng thái
- dispute không tồn tại
- deposit chưa khóa mà đã tranh chấp
- approvedCost vượt quá tiền cọc khóa
- owner/admin không đúng ngữ cảnh
- contract đã hoàn thành nhưng vẫn cố xử lý lại

15) Giữ idempotency ở mức hợp lý
Tránh tạo trùng:
- không cho tạo nhiều damage claim mở cho cùng 1 contract
- không cho admin ra quyết định nhiều lần trên cùng 1 dispute đã đóng
- không cho trả xe nhiều lần khi contract đã ở sau bước trả xe

16) Output mong muốn
Sau khi sửa xong, hãy trả:
- danh sách file đã sửa
- tóm tắt từng thay đổi
- SQL migration nếu có
- ví dụ request/response cho 4 API mới
- giải thích ngắn cách chạy test flow:
  1. tạo booking
  2. tạo contract
  3. lock deposit
  4. return vehicle
  5. damage claim
  6. admin confirm no damage
  7. kiểm tra overview + chain + DB mirror

17) Tiêu chuẩn code
- Giữ phong cách code gần với file hiện tại
- Không thêm thư viện nặng nếu không cần
- Hàm ngắn, tên rõ
- Comment ngắn ở đoạn logic quan trọng
- Không xóa flow cũ
- Ưu tiên sửa đủ để chạy được end-to-end

Hãy bắt đầu bằng cách đọc cấu trúc hiện có, sau đó tạo và sửa code vào folder backend2 và hiển thị diff rõ ràng.