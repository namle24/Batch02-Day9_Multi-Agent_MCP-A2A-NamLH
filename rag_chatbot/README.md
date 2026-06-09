# Day09 RAG Chatbot UI

Chatbot UI mới cho Day09, tái sử dụng RAG pipeline từ Day08 trong folder nội bộ:

```text
day08_rag_pipeline/
├── src/    # retrieval, reranking, generation helpers từ Day08
└── data/   # standardized docs + vectorstore chunks
```

## Chạy UI

```bash
uv run uvicorn rag_chatbot.server:app --reload --port 8501
```

Mở:

```text
http://localhost:8501
```

## Điểm nâng cấp so với Day08

- Chat được theo hội thoại, có gửi lịch sử gần nhất vào prompt.
- Vẫn dùng Day08 hybrid retrieval làm evidence/context.
- Trả lời bằng LLM qua OpenRouter khi có `OPENROUTER_API_KEY`.
- Có offline fallback để demo retrieval khi thiếu key.
- Ghi performance từng lượt vào `data/performance/chat_metrics.jsonl`.
- UI hiển thị latency: retrieval, generation, total, p95, fastest, recent runs.

## Tối ưu performance

- Retrieval được cache bằng `lru_cache`.
- Câu hỏi lặp lại hoặc giống nhau sẽ cho `cached_retrieval=true`.
- Metrics có thể dùng để so sánh lượt đầu với lượt cached trong demo.

## Cập nhật dữ liệu Day08 trong Day09

Khi thêm bài báo mới, điền URL vào:

```text
day08_rag_pipeline/data/landing/news/article_urls.txt
```

Sau đó chạy lại pipeline:

```bash
uv run python -m day08_rag_pipeline.src.task2_crawl_news
uv run python -m day08_rag_pipeline.src.task3_convert_markdown
uv run python -m day08_rag_pipeline.src.task4_chunking_indexing
```

Nếu chỉ thêm PDF hoặc JSON thủ công vào `day08_rag_pipeline/data/landing/`, chỉ cần chạy 2 lệnh cuối.

Ghi chú UI:
- Kết quả từ `news` hiển thị link bài báo.
- Kết quả từ `legal` hiển thị tên văn bản luật/PDF, chatbot sẽ nêu rõ luật/điều khi context có.

## Chọn model trên giao diện

UI gọi `/api/models` để lấy danh sách model. Có thể cấu hình thêm model trong `.env`:

```bash
OPENROUTER_MODEL=anthropic/claude-sonnet-4-5
OPENROUTER_MODEL_OPTIONS=openai/gpt-4o-mini,google/gemini-2.5-flash,anthropic/claude-3.5-haiku
```

Trên giao diện cũng có lựa chọn `Custom model...` để nhập trực tiếp model id của OpenRouter cho từng lượt chat. Performance log sẽ lưu model ở mỗi request để so sánh tốc độ/chất lượng.
