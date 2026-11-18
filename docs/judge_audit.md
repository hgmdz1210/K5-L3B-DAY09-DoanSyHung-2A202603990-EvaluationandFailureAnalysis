# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`
Dương tính (positive) là `FAIL`, vì việc của judge là tìm lỗi. Dữ liệu là replay công khai (n=100 mỗi file, 30 FAIL do người gán).

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | **Đạt** cả 3 (tp 24, fp 4, fn 6, tn 66) | **Dùng**, ở chế độ tham khảo (không blocking); tiền/approval vẫn chấm bằng code |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **Không đạt** κ (0.375 < 0.6) và R (0.300 < 0.7); chỉ P đạt (tp 9, fp 0, fn 21, tn 70) | **Loại**, không được làm gate |

Tỉ lệ FAIL sau hiệu chỉnh Rogan-Gladen: `tone_ok` quan sát 0.28, hiệu chỉnh 0.30; `helpful` quan sát 0.09, hiệu chỉnh 0.30 (judge `helpful` đánh giá thấp tỉ lệ lỗi thật gấp 3,3 lần).

## ≥5 case audit thủ công (judge_tone, 10/10 bất đồng đã xem)
Judge `tone_ok` bất đồng với người ở 10 dòng (6 lần judge quá dễ, 4 lần judge quá khó).

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | **Người** | Xưng "em" + "nha" quá suồng sã; judge nhầm là "thân thiện". Rubric: cấm tự xưng "em" và đuôi "nha/nhé" thay cho "ạ"; thân thiện ≠ suồng sã |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha." | PASS | FAIL | **Người** | Gọi khách là "bạn" + "nha". Rubric: bắt buộc xưng hô "anh/chị" |
| 3 | H-029 "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | **Người** | Giọng ra lệnh ("không cần nhắn thêm"), judge chỉ bám vào "Dạ, vui lòng". Rubric: cấm câu mệnh lệnh phủ định đối với khách |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | **Người** | Ngắn nhưng đủ ý và lịch sự; judge phạt vì "thiếu xin lỗi". Rubric: chỉ bắt xin lỗi khi từ chối hoặc có lỗi của LogiX, không bắt cho câu báo kết quả thường |
| 5 | H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | **Người** | "refund" được CS LogiX cho phép; judge phạt vì tiếng Anh. Rubric: thêm bảng thuật ngữ cho phép (`refund`) |
| 6 | H-063 "Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | **Người**, nhưng đây không phải lỗi giọng điệu | Lời hứa "sẽ hoàn thêm" vượt ngoài kết quả hệ thống (nhóm FM-08). Không sửa rubric tone; chuyển sang grader code kiểm tra lời hứa so với ledger |
| 7 | H-070 "...cho đơn O-909 ạ 😂😂" | PASS | FAIL | **Người** | Emoji cười trong ngữ cảnh khiếu nại. Rubric: cấm emoji |
| 8 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | **Judge** (theo ghi chú trong CSV) | Người đọc nhầm ticket nên nhãn sai: cần sửa nhãn thành FAIL. Lưu ý: lỗi ở đây là nội dung (từ chối sai) chứ không phải giọng, nên không thuộc `tone_ok`. Nếu sửa nhãn: P 0.893, R 0.806, κ 0.784 |
| 9 | H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ cho đơn O-233 ạ." | FAIL | PASS | **Người** (nhẹ) | Lặp "Dạ" là lỗi gõ, không phải giọng điệu. Rubric: lỗi chính tả đơn lẻ không tính vào tone |
| 10 | H-094 "Da, LogiX da hoan 40.000đ cho don O-341, xin loi vi su bat tien." | PASS | FAIL | **Người** | Mất toàn bộ dấu tiếng Việt (dịch máy); judge không phạt. Rubric: câu trả lời phải có dấu tiếng Việt |

Tổng: người đúng 9/10 (trong đó H-063 là lỗi nội dung, không phải tone), judge đúng 1/10 (H-081). Mẫu lỗi của judge: nó **rộng rãi** với giọng suồng sã/ra lệnh/emoji/mất dấu (5 trong 6 fn) và **cứng nhắc** với những thứ rubric chưa nói rõ (xin lỗi, từ tiếng Anh, lỗi gõ).

## Vì sao `helpful` không được làm gate (cột ma trận nhầm lẫn)
- tp 9, fp 0, **fn 21**, tn 70. Judge bắt được 9 trong 30 lỗi thật (**R = 0.30 < 0.7**); κ = 0.375 < 0.6.
- Precision = 1.0 là con số đánh lừa: judge hầu như không bao giờ nói FAIL, nên khi nói thì đúng, nhưng 70% lỗi lọt qua.
- 21 lỗi lọt có cùng một nguyên nhân: 18 dòng là **reply nói số tiền khác ledger** (ví dụ HL-015 reply 55.000đ, ledger 40.000đ; HL-020 reply 90.000đ, ledger 120.000đ) và 3 dòng reply cụt "Ok bạn, đơn … xử lý rồi nhé" (HL-047, HL-091, HL-097). Đây đúng là FM-08 (`misreport`): judge chỉ đọc reply nên không thể phát hiện số sai, vì nó **không nhìn thấy ledger**. Nhiều reply sai số còn kèm lời xin lỗi dài, lặp ý; có thể judge bị cuốn theo độ lịch sự, nhưng CSV không đủ để chứng minh điều này.
- Hậu quả nếu dùng làm gate: tỉ lệ lỗi thật là 0.30 nhưng judge chỉ thấy 0.09; một PR làm tăng số reply sai tiền vẫn qua. Với tiền thì grader phải là code (metric `reply_matches_ledger` ở M3, `RefundAmountCorrect`).

## Kết luận
- **Tiêu chí bị loại: `helpful`**, vì R = 0.30 và κ = 0.375 dưới floor; dẫn ma trận nhầm lẫn ở trên (fn = 21, toàn bộ là reply sai số hoặc cụt mà judge không có ledger để so).
- **`tone_ok` được dùng** vì qua cả 3 floor, nhưng chỉ ở chế độ tham khảo và sau khi sửa rubric theo bảng audit (xưng hô anh/chị, cấm "em/bạn/nha", cấm emoji, bắt buộc có dấu, cấm mệnh lệnh, xin lỗi chỉ khi cần, cho phép `refund`). Sửa nhãn H-081.
- **Nếu κ không xác định** (judge hằng số) thì `cohen_kappa` ném `ValueError` và `judge.py` coi là FAIL, không để judge "qua" nhờ tính kỹ thuật.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai (100 dòng, chỉ 30 FAIL), nên các ước lượng P/R có khoảng tin cậy rộng và recall 0.8 có thể dao động nhiều; cần nhãn người mới, held-out, để biết judge có tổng quát hoá không. Ghi chú trong CSV là do người gán nhãn viết nên cũng cần kiểm lại độc lập.
