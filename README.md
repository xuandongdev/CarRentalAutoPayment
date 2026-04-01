# Thực nghiệm đánh giá blockchain cho hệ thống thuê xe tự động thanh toán

## 1. Mục tiêu

Bộ thực nghiệm này dùng để đánh giá thành phần blockchain của hệ thống thuê xe tự động thanh toán theo đúng 5 nhóm yêu cầu:

1. `Performance`
2. `Scalability`
3. `Resilience`
4. `Security`
5. `Resource & Cost`

Khác với phiên bản trước, đầu ra cuối cùng đã được rút gọn để trực quan hơn:

- chỉ giữ **một file CSV chính** là `blockchain_evaluation.csv`
- chỉ chọn **một cấu hình lặp đại diện** là `20` lần chạy
- mỗi nhóm đánh giá có **một hình riêng** để mô tả kết quả

## 2. Vì sao chọn 20 lần lặp

Trong quá trình mô phỏng, hệ thống có thể chạy ở các mức lặp `5`, `10`, `20`. Tuy nhiên, để phần kết quả cuối cùng dễ đọc và có độ tin cậy cao hơn, cấu hình `20` lần lặp được chọn làm cấu hình đại diện vì:

- có cỡ mẫu lớn nhất
- ổn định hơn khi tính trung bình và độ lệch chuẩn
- giúp biểu đồ gọn hơn, không phải chồng nhiều đường trên cùng một chart

## 3. Tệp đầu ra chính

Sau khi chạy script, bộ tệp được sử dụng chính là:

- `blockchain_evaluation.csv`
- `performance_evaluation.png`
- `scalability_evaluation.png`
- `resilience_evaluation.png`
- `security_evaluation.png`
- `resource_cost_evaluation.png`

## 4. Cách chạy lại thực nghiệm

```powershell
python blockchain_evaluation_script.py
```

Script sẽ:

- sinh dữ liệu mô phỏng
- chọn cấu hình `20` lần lặp làm kết quả cuối cùng
- xuất `blockchain_evaluation.csv`
- vẽ lại toàn bộ 5 biểu đồ

## 5. Ý nghĩa của file CSV

File `blockchain_evaluation.csv` là dữ liệu tổng hợp cuối cùng. Trong đó:

- mỗi dòng thuộc về một nhóm đánh giá cụ thể
- các giá trị `*_mean` là trung bình của `20` lần mô phỏng
- các giá trị `*_std` là độ lệch chuẩn
- các giá trị `*_cv` là hệ số biến thiên dùng để đánh giá độ ổn định tương đối

## 6. Tài liệu mô tả chi tiết

Phần mô tả học thuật chi tiết cho từng biểu đồ đã được viết trong:

- `blockchain_evaluation_table.md`

Tệp này trình bày lại đầy đủ theo đúng khung:

- nhóm thực nghiệm
- kịch bản chi tiết
- độ đo chính
- phân tích trung bình
- phân tích độ lệch chuẩn
- đánh giá riêng từng chart
- đánh giá chung toàn bộ hệ thống

## 7. Lưu ý

Các kết quả hiện tại là **mô phỏng có kiểm soát**, không phải benchmark trực tiếp từ hệ thống triển khai thật. Vì vậy, chúng phù hợp để phân tích xu hướng, minh họa phương pháp thực nghiệm và dùng trong báo cáo, nhưng chưa nên xem là kết quả đo thực địa cuối cùng.
