# Lab Assignment - Day08 Supervisor Workers

## Mục tiêu

Cải tiến chatbot/RAG Day08 bằng pattern **Supervisor - Workers**.

Kiến trúc gồm 1 supervisor và 3 workers:

| Thành phần | Vai trò |
|---|---|
| `Supervisor` | Nhận câu hỏi, quyết định route, gọi workers, tổng hợp câu trả lời |
| `LegalWorker` | Tìm evidence trong nhóm văn bản pháp luật Day08 |
| `NewsWorker` | Tìm evidence trong nhóm bài báo/tin tức Day08 |
| `ConversationWorker` | Xử lý intent hội thoại hoặc câu hỏi chung |

## Cách chạy CLI demo

```bash
uv run python Lab_Assignment/run_demo.py
```

Chạy với câu hỏi riêng:

```bash
uv run python Lab_Assignment/run_demo.py --question "Hành vi tàng trữ ma túy bị xử lý thế nào?"
```

## Cách chạy web demo

```bash
uv run uvicorn Lab_Assignment.app:app --host 127.0.0.1 --port 8510
```

Mở:

```text
http://127.0.0.1:8510
```

## Điểm cải tiến so với Day08

- Day08 chủ yếu là pipeline retrieval/generation tuyến tính.
- Assignment này thêm Supervisor để quyết định gọi worker nào.
- Tách nhiệm vụ rõ ràng giữa legal/news/conversation workers.
- Có trace để xem supervisor gọi worker nào.
- Có latency tổng và latency từng worker.
- Có fallback offline nếu chưa có `OPENROUTER_API_KEY`.

## File chính

- `supervisor_workers.py`: core Supervisor - Workers.
- `run_demo.py`: CLI demo.
- `app.py`: FastAPI app.
- `static/index.html`: giao diện demo.

