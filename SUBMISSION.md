# Nộp bài

- Họ tên: Đinh Phúc Diên
- MSSV: 2A202603876
- Lớp: K5-L3B, Day 11
- Repo: https://github.com/dinhphucdien179/K5-L3B-Day11-DinhPhucDien-2A202603876-Guardrails-HITL-Responsible-AI

## File kết quả

Hai file chấm chính:

- `outputs/results.json`: kết quả phòng thủ của Blue ở CP3, khớp `schemas/results.schema.json`.
- `outputs/attack_results.json`: kết quả tấn công Red và Red Advance ở CP4, có ghi `llm_provider` và `llm_model`.

File đi kèm:

- `outputs/audit_log.json`, `outputs/metrics.json`: sinh cùng lúc với `results.json`.
- `outputs/unsafe_attack_result.json`, `outputs/guards_attack_result.json`: chi tiết từng prompt trên Red và Red Advance.
- `outputs/api_usage.json`: số lượt gọi model đã dùng (33/100).
- `outputs/hitl_demo.json`, `outputs/hitl_approvals.json`: kết quả demo HITL, phần tham khảo.
- `outputs/grade_report.json`, `outputs/lab_report.md`: do `scripts/grade.py` tự sinh.

Tất cả đều do lệnh lab tạo ra, em không sửa tay file nào.

## Những gì em đã kiểm tra

- [x] `pytest tests/smoke tests/public tests/unit -q`: 92 passed.
- [x] `python scripts/grade.py --submission-dir . --out outputs/grade_report.json`: `technical_failure: false`, schema hợp lệ, public tests 10/10 pass.
- [x] `results.json` có 5 câu an toàn, 7 câu tấn công, 3 edge case và phần rate limit (gửi 15 = 10 qua + 5 bị chặn).
- [x] `attack_results.json` có 5 kết quả cho Red và 5 cho Red Advance, ghi đúng `gemini` / `gemini-3.5-flash-lite` như trong `.env` lúc chạy.
- [x] `.env` nằm trong `.gitignore`, không có trong commit; `.env.example` không chứa key thật.
- [x] Không sửa giá trị trong `data/protected/vinbank_secrets.json`.

## Thông tin cho người chấm khi replay

- Blue dùng OpenRouter `openai/gpt-4o-mini`, cố định trong `src/core/config.py`, cần `OPENROUTER_API_KEY`.
- Red và Red Advance dùng `RED_TEAM_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.5-flash-lite`, cần `GOOGLE_API_KEY`. NeMo self-check của Red Advance dùng cùng key và model này.
- Mỗi lần chạy `src/main.py` mặc định được đếm vào `outputs/api_usage.json` với giới hạn 100 lượt. Đặt `LAB_LIVE_API=0` để tắt bộ đếm khi replay.
- Bonus: Red Advance chưa bị leak nên em xét B1 (leak trên Red).
