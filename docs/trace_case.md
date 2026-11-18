# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `<shape> <claim>@<seed>`, run ID trong report |
| Triệu chứng | Grader nào fail; reply nói gì so với ledger ghi gì |
| Bước sai đầu tiên | Số thứ tự event + kind + trích payload (≤1 dòng) |
| Vì sao là bước *đầu tiên* | Các bước trước đó đúng ra sao (dẫn số event) |
| Failure mode | Mã FM-xx trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng claim@seed trên shape `fixed`: bước đó khác thế nào |
| Regression test | Tên test + grader/assert nào bắt được; đã thấy fail trên variant lỗi và pass trên `fixed` chưa |
| Chưa chắc chắn | Điều trace không chứng minh được |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.

---

# Case của tôi: C-002@11

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`. Dựng lại bằng `python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11`. Run ID `E-seeded_regression-20261118-871b` (`reports/eval_seeded_regression.json`, row `E-002` seed 11; trace `R-seeded_regression-C-002-s11`) |
| Triệu chứng | Grader Lab 8 FAIL `status resolved != denied`. Ledger ghi `refund_vnd=20000`, `refund_count=1`; nhãn là `denied`, refund 0. Reply (event 6) nói "LogiX đã hoàn 20.000đ cho đơn O-202" nên reply khớp ledger, chỉ có quyết định là sai |
| Bước sai đầu tiên | Event 3 `model_override {"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` đúng phạm vi (`owner_order_only`). Event 2 `investigator` đọc đúng DB: `O-202 delay_days: 2`, `shipping_fee_vnd: 20000`. Đến event 3 agent mới ghi đè 2 thành 5 theo ticket ("giao trễ 5 ngày"). Event 4 `quote` (20.000đ, clause `SHIP-LATE-03`) và event 6 chỉ là hệ quả của số ngày bị ghi đè |
| Failure mode | **FM-03** `ticket_trust` (`variant_agent.py:144` `trusts_ticket`) |
| Đối chứng | `fixed C-002@11`: không có event `model_override`; event 3 `quote {amount_vnd: 0, reason: no_entitlement, clause_ids: []}`; reply "chưa đủ điều kiện hoàn"; ledger 0, status `denied`, grader Lab 8 PASS |
| Regression test | `tests/test_lab9_trace_case.py` (2 test, marker `student`, chạy trong job `eval-gate`): `test_ticket_trust_is_caught_on_seeded_regression` assert event 3 là `model_override {delay_days: 5}`, ledger 20.000 khác nhãn 0, status `resolved` khác `denied`; `test_fixed_keeps_the_db_fact` assert `fixed` không có `model_override`, ledger 0, `denied`. Đã chạy: cả hai pass (fail trên variant lỗi được khẳng định bằng assert, pass trên `fixed`) |
| Chưa chắc chắn | (1) `seeded_regression` bật cùng lúc `ticket_trust`, `pre_deducted`, `ignore_denied`; tôi quy lỗi ở C-002 cho `ticket_trust` vì event `model_override` xuất hiện ngay trước quote, nhưng chưa chạy từng lỗi riêng. (2) Đã chạy đủ 5 seed. `seeded_regression C-002` sai ở cả 5 seed (`variant_agent.py:144`: `ticket_trust` bật vô điều kiện). Baseline `swarm` cũng mang đúng lỗi FM-03 nhưng chỉ khi `seed % 5 == 0`, tức `swarm C-002@55` FAIL (event 3 `model_override {delay_days: 5}`) còn @11/22/33/44 PASS; `fixed` PASS cả 5. Vì vậy `swarm@55` là trial FAIL thật nằm trong baseline v1, và test cũng khẳng định nó. (3) Bug `quiet_override` cũng là FM-03 nhưng không ghi event `model_override`, nên test này không bắt được; cần assert trên ledger (`RefundAmountCorrect`, M3) để bắt cả hai |
