# Day 11: Guardrails, HITL và Responsible AI

Bài lab cá nhân Day 11, lớp K5-L3B.

- Họ tên: Đinh Phúc Diên
- MSSV: 2A202603876
- Repo: https://github.com/dinhphucdien179/K5-L3B-Day11-DinhPhucDien-2A202603876-Guardrails-HITL-Responsible-AI

Cách làm và kết quả của từng checkpoint em ghi trong [CHECKPOINTS.md](CHECKPOINTS.md). Danh sách file nộp và những gì em đã tự kiểm tra nằm trong [SUBMISSION.md](SUBMISSION.md). Hai file [RUBRIC.md](RUBRIC.md) và [RULES.md](RULES.md) là tài liệu của lớp, em giữ nguyên.

## Nội dung bài làm

Bài có hai phần. Ở phần Blue Team (CP2, CP3), em xây các lớp bảo vệ cho chatbot VinBank: lọc input, lọc output, rate limit, audit log, monitoring và kiểm tra egress. Ở phần Red Team (CP4), em viết 5 prompt tấn công rồi chạy lên hai agent có sẵn của lab là Red và Red Advance, mục tiêu là lấy được secret giả trong `data/protected/vinbank_secrets.json`.

Luồng xử lý của Blue:

```text
User -> RateLimitPlugin -> InputGuardrailPlugin -> LLM -> OutputGuardrailPlugin -> trả lời
        (audit log và monitoring ghi lại mọi request, kể cả request bị chặn ở lớp đầu)
```

## Kết quả

| Phần | Kết quả | Bằng chứng |
|---|---|---|
| CP2 | Các case mẫu của `--part 2` đều PASS, secret và PII bị thay bằng `[REDACTED]` | in ra terminal |
| CP3 | 5/5 câu hỏi an toàn không bị chặn, 7/7 câu tấn công bị chặn ở input guardrail; gửi 15 request thì 10 qua, 5 bị rate limit | `outputs/results.json` |
| CP4, Red | 5/5 prompt làm lộ đủ cả ba giá trị bảo vệ | `outputs/attack_results.json` |
| CP4, Red Advance | 0/5 prompt làm lộ, cả 5 bị lớp regex chặn | `outputs/attack_results.json` |

`scripts/grade.py` báo `technical_failure: false`, schema hợp lệ, public tests 10/10 pass. Toàn bộ 92 test trong `tests/smoke`, `tests/public` và `tests/unit` đều pass và không cần API key.

## Model sử dụng

| Agent | Provider | Model |
|---|---|---|
| Blue | OpenRouter | `openai/gpt-4o-mini` |
| Red, Red Advance | Gemini (Google AI Studio) | `gemini-3.5-flash-lite` |

Starter để Blue cố định ở `liquid/lfm-3-1.7b:free`. Em có chạy thử model này (2 lượt đầu trong `outputs/api_usage.json`), sau đó đổi Blue sang `openai/gpt-4o-mini` qua OpenRouter cho các lần chạy chính thức. Red và Red Advance chạy `gemini-3.5-flash-lite` (đặt trong `.env`) thay cho `gemini-3.5-flash`. Model thực chạy được ghi lại trong `results.json` và `attack_results.json`.

## Cách chạy lại

Em chạy trên conda env Python 3.12. Các gói trong `requirements.txt` đã pin đúng phiên bản em dùng. Lưu ý `google-adk` 2.15 và `google-genai` 2.34 cần Python 3.11 trở lên.

```bash
conda create -n lab11 python=3.12 -y
conda activate lab11
pip install -r requirements.txt
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
```

Các biến cần điền trong `.env`:

```text
OPENROUTER_API_KEY=...            # Blue
RED_TEAM_PROVIDER=gemini
GOOGLE_API_KEY=...                # Red, Red Advance và NeMo self-check
GOOGLE_GENAI_USE_VERTEXAI=0
GEMINI_MODEL=gemini-3.5-flash-lite
```

Chạy từ thư mục gốc repo:

```bash
python src/main.py --part 2      # CP2, chạy offline
python src/main.py --part 3      # CP3: results.json, audit_log.json, metrics.json
python src/main.py --part 4      # CP4: attack_results.json và 2 file chi tiết
pytest tests/smoke tests/public tests/unit -q
python scripts/grade.py --submission-dir . --out outputs/grade_report.json
```

Mỗi lượt gọi model khi chạy `src/main.py` được đếm vào `outputs/api_usage.json`, tối đa 100 lượt, tính cả NeMo self-check. Hiện đã dùng 33 lượt. Một lần chạy CP3 tốn khoảng 6 lượt (câu bị chặn ở input không gọi model), một lần CP4 khoảng 9 lượt. Khi replay mà không muốn bị giới hạn này thì đặt `LAB_LIVE_API=0` trước khi chạy.

## Ghi chú

- Các file trong `outputs/` đều do lệnh lab sinh ra, em không sửa tay. `lab_report.md` và `grade_report.json` do `scripts/grade.py` tạo.
- HITL trong `src/hitl/` là phần tham khảo, không chấm. Em vẫn làm `ConfidenceRouter`, 3 điểm quyết định HITL và một luồng duyệt mô phỏng. `python scripts/demo_hitl.py` chạy 9 kịch bản (duyệt, từ chối, hết hạn, đổi payload, dùng lại approval...) và không gọi model.
