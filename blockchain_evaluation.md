# Đánh giá chi tiết bộ thực nghiệm blockchain cho CarRentalAutoPayment

## 1. Mục tiêu và cách quét code

Bộ thực nghiệm này được làm lại từ đầu sau khi quét codebase và chọn đúng thành phần có thể đo được.

### 1.1. Thành phần được chọn làm lõi thực nghiệm

- `backend2/modules/node_storage.py`: local blockchain storage có khả năng tạo transaction, mine block, ghi block, tx index và state snapshot.
- `backend2/modules/utils.py`: cung cấp `sha256_obj`, `calc_merkle_root`, `stable_json`; đây là phần cần để kiểm tra tính hợp lệ của block trong fault emulation.
- `backend2/modules/service.py`: được dùng để suy ra các flow nghiệp vụ low/medium/high cho phần Resource & Cost.
- `backend2/FLOW.md`: được dùng để map các bước nghiệp vụ thành các tx types và kịch bản test.

### 1.2. Thành phần không được chọn làm cơ sở benchmark

- `server/Block.py` có lỗi tên thuộc tính (`blockID` nhưng hash lại đọc `block_id`).
- `server/SmartContract.py` có nhiều thuộc tính chưa khởi tạo đúng cách.
- Vì vậy, bộ thực nghiệm này đặt trên `backend2/modules/node_storage.py`, là phần local chain ổn định hơn và có thể chạy lặp được.

## 2. Môi trường và nguyên tắc thực nghiệm

- Mỗi kịch bản được lặp lại `5` lần.
- Mỗi lần chạy dùng thư mục tạm riêng, tránh ảnh hưởng giữa các lần đo.
- Tất cả node local được tạo đồng nhất trên cùng máy, cùng Python runtime và cùng logic ghi file.
- Do đây là cụm local, độ trễ mạng thực tế được emulation bằng software delay trong các bài scalability/resilience; không có `tc` hay network namespace thật.

## 3. Lưu ý phương pháp luận

- `Performance`, `Scalability` và một phần `Resource & Cost` là đo trực tiếp trên local storage engine.
- `Resilience` và `Security` là fault emulation dựa trên block format, replication và quorum model, vì code hiện tại không có consensus/network layer đầy đủ.
- `Success Rate` trong biểu đồ Performance được hiểu là tỉ lệ giao dịch đạt SLA xác nhận <= `5600 ms`, không phải tỉ lệ eventual write.
- `Gas/Fee` và `Energy` trong nhóm Resource & Cost là proxy metrics vì code hiện tại không có gas accounting native và không phải PoW.

## 4. Khung thực nghiệm

| Nhóm thực nghiệm | Kịch bản chi tiết | Độ đo chính |
| --- | --- | --- |
| Performance | Tăng dần tải giao dịch từ 100 đến 3500 giao dịch/block | TPS, Latency, Success Rate |
| Scalability | Giữ nguyên 100 giao dịch/block, tăng số node lên 4, 8, 16, 32 | Throughput/Node, Propagation Time, Storage Overhead |
| Resilience | Giả lập `Network Partition` và `Validator Down` trên cụm 8 node | Downtime, Consensus Recovery, Fork Rate |
| Security | Giả lập 10-validator committee, tăng tỉ lệ Byzantine từ 10% đến 50% | Fault Tolerance, Attack Cost, Double Spend Window |
| Resource & Cost | Chạy flow contract `Low`, `Medium`, `High` dựa theo số tx và payload | Gas/Fee Proxy, CPU, RAM, Bandwidth, Energy Proxy |

## 5. Cách đọc độ lệch chuẩn

- `mean`: giá trị trung bình của 5 lần lặp.
- `std`: độ lệch chuẩn, cho biết mức dao động tuyệt đối.
- `cv = std / mean`: cho biết mức dao động tương đối.
- Quy ước đọc:
  - `cv < 5%`: rất ổn định
  - `5% <= cv < 10%`: ổn định khá
  - `cv >= 10%`: dao động đáng kể

## 6. Phân tích chi tiết từng biểu đồ

### 6.1. Performance (`performance_evaluation.png`)

Mỗi lần đo tạo từ `100` đến `3500` giao dịch, dùng `LocalNodeStorage.make_tx()` để sinh giao dịch và `mine_block()` để xác nhận chung vào một block.

| Load | TPS mean | TPS std | TPS CV (%) | Latency mean (ms) | Latency std | Latency CV (%) | Success mean (%) | Success CV (%) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 100 | 468.63 | 21.24 | 4.53 | 198.75 | 10.07 | 5.06 | 100.00 | 0.00 |
| 500 | 503.49 | 21.91 | 4.35 | 921.15 | 42.10 | 4.57 | 100.00 | 0.00 |
| 1000 | 512.90 | 22.37 | 4.36 | 1801.32 | 78.98 | 4.38 | 100.00 | 0.00 |
| 1500 | 516.96 | 7.35 | 1.42 | 2674.06 | 43.26 | 1.62 | 100.00 | 0.00 |
| 2000 | 506.90 | 23.52 | 4.64 | 3651.90 | 185.72 | 5.09 | 100.00 | 0.00 |
| 2500 | 515.11 | 11.23 | 2.18 | 4469.74 | 77.57 | 1.74 | 100.00 | 0.00 |
| 3000 | 500.41 | 19.03 | 3.80 | 5543.04 | 229.41 | 4.14 | 55.26 | 44.93 |
| 3500 | 504.72 | 13.89 | 2.75 | 6408.35 | 183.12 | 2.86 | 0.00 | N/A |

- Ở tải `100`, hệ thống đạt trung bình `TPS = 468.63` và `Latency = 198.75 ms`.
- Ở tải `3500`, TPS vẫn quanh `504.72` nhưng latency tăng lên `6408.35 ms`.
- Tính trên toàn dải tải, TPS tăng nhẹ khoảng `7.70%` và gom vào một vùng trần quanh `500 TPS`.
- Latency tăng `32.24` lần từ load đầu đến load cuối.
- `Success Rate` giảm mạnh khi vượt vùng block cần xử lý trong `5600 ms`.

Đánh giá độ lệch chuẩn:

- `TPS cv` chỉ dao động khoảng `1.42%` đến `4.64%`, tức là thấp và khá ổn định.
- `Latency cv` nằm khoảng `1.62%` đến `5.09%`; nhìn chung vẫn thấp, nhưng nhạy hơn khi tải tăng.
- `Success Rate` dao động mạnh nhất ở vùng sát ngưỡng SLA.

Kết luận: Performance của storage engine này giữ được throughput khá ổn định, nhưng khi block quá lớn thì lỗi không nằm ở TPS mà nằm ở latency và khả năng đạt SLA.

### 6.2. Scalability (`scalability_evaluation.png`)

Một leader mine `100` giao dịch/block, sau đó replicate cùng block đó đến các peer local.

| Nodes | Throughput/node mean | Throughput std | Propagation mean (s) | Propagation std | Storage mean (MB) | Storage CV |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | 31.99 | 1.39 | 0.606 | 0.029 | 0.54 | 0.00 |
| 8 | 8.00 | 0.36 | 1.392 | 0.072 | 1.08 | 0.00 |
| 16 | 1.96 | 0.09 | 3.007 | 0.119 | 2.16 | 0.00 |
| 32 | 0.49 | 0.01 | 6.151 | 0.104 | 4.31 | 0.00 |

- Khi tăng từ `4` lên `32` node, `Throughput/Node` giảm rất mạnh.
- `Propagation Time` tăng theo số node do replication fan-out.
- `Storage Overhead` tăng gần tuyến tính theo số node.

Đánh giá độ lệch chuẩn:

- `Throughput/Node cv`: thấp, khá ổn định.
- `Propagation Time cv`: thấp đến vừa.
- `Storage Overhead cv`: gần như bằng `0`, vì chi phí lưu trữ tăng gần xác định theo số node.

Kết luận: Kết quả mới cho thấy scalability thực tế giảm theo số node nếu tính theo hiệu suất trên mỗi node, hợp lý hơn mô phỏng cũ.

### 6.3. Resilience (`resilience_evaluation.png`)

| Scenario | Downtime mean (s) | Downtime std | Recovery mean (s) | Recovery std | Fork mean | Fork CV |
| --- | --- | --- | --- | --- | --- | --- |
| Network Partition | 1.142 | 0.008 | 0.683 | 0.016 | 0.500 | 0.00 |
| Validator Down | 0.305 | 0.021 | 0.476 | 0.023 | 0.000 | N/A |

- `Network Partition` có `Downtime = 1.142 s`, lớn hơn rõ so với `Validator Down = 0.305 s`.
- `Consensus Recovery` của partition cao hơn vì phải giải quyết hai đầu chain cạnh tranh.
- `Fork Rate` của `Network Partition` xấp xỉ `0.5`, trong khi `Validator Down` bằng `0`.

Kết luận: Validator down phục hồi khá nhanh, nhưng network partition là điểm yếu rõ ràng hơn nhiều vì sinh chain divergence thật sự.

### 6.4. Security (`security_evaluation.png`)

| Byzantine % | Fault tolerance | Attack cost mean | Attack cost std | Window mean (s) | Window std |
| --- | --- | --- | --- | --- | --- |
| 10 | Pass | 1872.03 | 0.00 | 0.060 | 0.003 |
| 20 | Pass | 3744.06 | 0.00 | 0.055 | 0.009 |
| 30 | Pass | 5616.09 | 0.00 | 0.062 | 0.004 |
| 40 | Pass | 7488.12 | 0.00 | 0.067 | 0.002 |
| 50 | Fail | 9360.16 | 0.00 | 0.207 | 0.005 |

- Hệ thống `Pass` đến mức `Byzantine = 40%`.
- Hệ thống bắt đầu `Fail` từ `Byzantine = 50%`.
- `Attack Cost` tăng gần như tuyến tính theo số validator cần compromise.

Lưu ý bảo mật rất quan trọng từ code scan:

- `backend2/modules/node_storage.py::mine_block()` tạo `merkleRoot` và `hash` dựa trên `txHash`, không commit đầy đủ payload giao dịch.
- `backend2/modules/node_storage.py::make_tx()` tạo `signature` dựa trên `fromAddress`, `txType`, `rawData`; nó không cover trực tiếp `amount` và `toAddress`.

Kết luận: Nếu chỉ tính ngưỡng Byzantine theo quorum đã emulation, hệ thống chịu được tối đa khoảng `40%` validator ác ý và thất bại từ `50%`. Tuy nhiên, integrity của transaction payload trong code hiện tại yếu hơn thế và cần sửa thiết kế hash/signature.

### 6.5. Resource & Cost (`resource_cost_evaluation.png`)

| Complexity | Gas mean | CPU mean (%) | RAM mean (%) | Bandwidth mean (MB/s) | Energy mean (Wh) |
| --- | --- | --- | --- | --- | --- |
| Low | 1158.50 | 28.71 | 0.00 | 0.23 | 0.0001 |
| Medium | 4085.01 | 13.54 | 0.01 | 0.58 | 0.0000 |
| High | 13190.58 | 70.13 | 0.03 | 1.52 | 0.0003 |

- `Gas/Fee proxy` tăng rất mạnh từ `Low` sang `High`.
- `CPU` và `Bandwidth` cũng tăng rõ khi flow tranh chấp đầy đủ được kích hoạt.
- `RAM` tăng ít hơn nhưng vẫn đi lên theo độ phức tạp payload.

Đánh giá độ lệch chuẩn:

- `Gas cv`: rất ổn định.
- `CPU cv`: nhạy cảm hơn do scheduler và file write timing.
- `RAM cv`: ổn định khá.
- `Bandwidth cv`: dao động vừa phải.

Kết luận: Chi phí vận hành tăng rất nhanh khi nghiệp vụ phức tạp hơn, nhất là ở flow tranh chấp đầy đủ.

## 7. Đánh giá tổng hợp

- Điểm mạnh: local storage engine lặp lại được, throughput khá ở tải vừa phải, validator-down phục hồi nhanh.
- Điểm yếu: latency tăng nhanh khi block lớn, scalability fan-out tốn propagation/storage, network partition tạo fork, security có vấn đề commitment.

## 8. Kết luận cuối cùng

Hệ thống blockchain của CarRentalAutoPayment đang mạnh ở vai trò local audit trail và file-based ledger nhẹ, nhưng chưa đạt mức blockchain phân tán hoàn chỉnh. Performance ở tải vừa phải là tốt, song latency vượt nhanh khi block lớn. Scalability thực tế giảm theo số node do replication cost. Resilience tồn tại điểm yếu rõ ở Network Partition. Nghiêm trọng nhất, lớp bảo mật transaction/block cần được thiết kế lại vì hash và signature chưa cover đầy đủ nội dung giao dịch.

## 9. Đề xuất cải tiến

1. Sửa transaction hash/signature để cover `amount`, `toAddress`, `fromAddress`, `rawData`, `timestamp`.
2. Sửa block hash và merkle root để commit vào full transaction digest, không chỉ là `txHash`.
3. Bổ sung consensus/validation layer thật nếu muốn đánh giá Byzantine và partition sát thực tế hơn.
4. Chia block theo chunk hoặc giới hạn số tx/block nếu muốn giữ SLA latency.
5. Nếu chạy trên local cluster/Docker, bổ sung network emulation bằng `tc`.
