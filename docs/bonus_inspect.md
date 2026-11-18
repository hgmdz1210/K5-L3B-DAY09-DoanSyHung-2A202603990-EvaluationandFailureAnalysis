# Bonus: port 3 grader sang Inspect AI và so kết quả

**Lệnh** (trong `src/`):
```bash
pip install -r requirements-bonus.txt        # inspect-ai==0.3.291, CI không cài
python -m lab9.bonus_inspect --shapes swarm,fixed,seeded_regression,flaky_regression,slice_regression,honest_refactor,probe_sibling_refund,probe_misreport
python -m pytest -q -m student -o addopts= tests/test_lab9_bonus_inspect.py
```

## Cách port (`src/lab9/bonus_inspect.py`)
| Khái niệm | pydantic-evals (harness chính) | Inspect AI (bản port) |
|---|---|---|
| Một trial | `Case` `E-xxx@seed` | `Sample(id="E-xxx@seed", target=<nhãn JSON>)` |
| Chạy agent | task `lab9.eval.make_task` | `@solver run_shape`: gọi cùng `make_task` trên store tạm, giữ Trial trong `state.store` |
| Model | MockLLM của Lab 8 | provider `mockllm/model` của Inspect (không gọi tới, solver không `generate`) |
| Grader | `Evaluator` trong `lab9.graders` | `@scorer` native, **viết lại độc lập**, không import `lab9.graders` |
| Tổng hợp | `aggregate`: safety = đếm, capability = trung bình | `@metric count()` cho `approval_bypass`; `mean()` cho hai metric còn lại |

3 grader được port: `approval_bypass` (an toàn, đếm), `refund_amount_correct` (đọc ledger), `reply_matches_ledger` (FM-08). Chạy `max_samples=1` để giữ tất định như `lab9.eval`. Log Inspect ghi vào `src/reports/inspect_logs/` (xem bằng `inspect view`).

## Kết quả so khớp (eval set v1, 14 item × 5 seed mỗi shape)
```
shape                 metric                    pydantic-evals  inspect-ai  agree
swarm                 approval_bypass                        0           0  70/70
swarm                 refund_amount_correct             0.9857      0.9857  70/70
swarm                 reply_matches_ledger                 1.0         1.0  70/70
fixed                 approval_bypass                        0           0  70/70
fixed                 refund_amount_correct                1.0         1.0  70/70
fixed                 reply_matches_ledger                 1.0         1.0  70/70
seeded_regression     approval_bypass                        0           0  70/70
seeded_regression     refund_amount_correct             0.8571      0.8571  70/70
seeded_regression     reply_matches_ledger              0.7857      0.7857  70/70
flaky_regression      approval_bypass                        0           0  70/70
flaky_regression      refund_amount_correct             0.9429      0.9429  70/70
flaky_regression      reply_matches_ledger                 1.0         1.0  70/70
slice_regression      approval_bypass                        0           0  70/70
slice_regression      refund_amount_correct             0.9571      0.9571  70/70
slice_regression      reply_matches_ledger                 1.0         1.0  70/70
honest_refactor       approval_bypass                        0           0  70/70
honest_refactor       refund_amount_correct                1.0         1.0  70/70
honest_refactor       reply_matches_ledger                 1.0         1.0  70/70
probe_sibling_refund  approval_bypass                       20          20  70/70
probe_sibling_refund  refund_amount_correct             0.7143      0.7143  70/70
probe_sibling_refund  reply_matches_ledger                 1.0         1.0  70/70
probe_misreport       approval_bypass                        0           0  70/70
probe_misreport       refund_amount_correct                1.0         1.0  70/70
probe_misreport       reply_matches_ledger              0.8571      0.8571  70/70
exit 0 — Inspect AI scorers agree with pydantic-evals on every trial
```

**560/560 trial khớp trên cả 3 grader** (8 shape × 70 trial), cả giá trị từng trial lẫn giá trị tổng hợp.

- Không variant công khai nào làm `approval_bypass` bật, nên "khớp 0 = 0" là vô nghĩa. Vì vậy có thêm 2 probe ghép từ công tắc lỗi có sẵn, chỉ đăng ký lúc chạy (không sửa `variants.py`): `probe_sibling_refund` (FM-07, bypass = 20 trial) và `probe_misreport` (FM-08, reply_matches_ledger 0.857). Hai framework vẫn khớp từng trial.
- Bộ so sánh không phải lúc nào cũng xanh: `test_comparison_reports_a_broken_port` cố ý làm hỏng bộ đọc số tiền của bản Inspect, và phép so sánh báo bất đồng ở `reply_matches_ledger`.

## Nhận xét
- Hai framework cho cùng kết quả vì cùng đọc một Trial tất định (MockLLM) và cùng quy tắc chấm; khác biệt chỉ ở hạ tầng: Inspect cho log `.eval` xem lại được từng sample (`explanation` ghi ledger/nhãn/số trong reply), pydantic-evals nhẹ hơn và nằm sẵn trong harness/CI.
- Port độc lập (không gọi lại `lab9.graders`) là điểm chính: nếu chỉ bọc lại cùng hàm thì "khớp" không chứng minh gì. Cái được kiểm là đặc tả của grader (đọc ledger, không đọc reply; safety là đếm; không có reply thì không có gì để nói sai).
- Giới hạn: hai bản port vẫn dùng chung regex đọc số tiền (`…đ`, `VND`, `đồng`), nên một lỗi chung ở đặc tả (ví dụ số viết bằng chữ) sẽ lọt cả hai. Chỉ port 3 grader code; judge (`tone_ok`) chưa được port.
