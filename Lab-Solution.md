# Lab Solution Day09

## 1. Các bài lab trên lớp

### Bài tập 1.1 - Thay đổi câu hỏi

Đã chạy được Stage 1 và có thể thay đổi biến câu hỏi trong `stages/stage_1_direct_llm/main.py` để kiểm tra Direct LLM.

Ý nghĩa:

- Stage 1 gọi trực tiếp LLM.
- Không có tools, không có memory, không có agent orchestration.
- Phù hợp câu hỏi đơn giản.

### Bài tập 1.2 - Thêm temperature control

Temperature được cấu hình qua LLM config/env để điều chỉnh độ sáng tạo của model.

- Temperature thấp: câu trả lời ổn định, phù hợp pháp lý.
- Temperature cao: câu trả lời đa dạng hơn nhưng dễ kém nhất quán.

### Bài tập 2.1 - Thêm knowledge base entry

Đã bổ sung entry `labor_law` trong `exercises/exercise_2_tools.py`.

Entry này hỗ trợ câu hỏi về:

- lao động;
- sa thải;
- hợp đồng lao động;
- termination/labor.

### Bài tập 2.2 - Tạo tool mới

Đã có tool `check_statute_of_limitations(case_type: str)` trong `exercises/exercise_2_tools.py`.

Tool trả về thời hiệu khởi kiện theo loại vụ án:

- `contract`: 4 năm;
- `tort`: 2-3 năm tùy bang;
- `property`: 5 năm.

### Bài tập 3.1 - Thêm tool tra cứu án lệ

Ý tưởng triển khai:

- Tạo tool `search_case_law(query: str)`.
- Tool tìm án lệ theo keyword.
- Gắn tool vào ReAct Agent để agent tự quyết định khi nào cần gọi.

### Bài tập 3.2 - Debug agent reasoning

Cách làm:

- Bật verbose/debug cho agent hoặc xem logs.
- Quan sát agent theo chu trình: Think -> Act -> Observe -> Answer.
- Mục tiêu là hiểu khi nào agent gọi tool và vì sao.

### Bài tập 4.1 - Thêm Privacy Agent

Đã implement `privacy_agent` trong `exercises/exercise_4_multiagent.py`.

Agent này chuyên phân tích:

- GDPR;
- data protection;
- privacy rights;
- data breach;
- nghĩa vụ thông báo;
- rủi ro xử phạt.

### Bài tập 4.2 - Implement conditional routing

Đã implement `check_routing` và `route_to_agents` trong `exercises/exercise_4_multiagent.py`.

Routing hiện tại:

- Có keyword `tax`, `irs`, `thuế` -> gọi `tax_agent`.
- Có keyword `compliance`, `sec`, `regulation` -> gọi `compliance_agent`.
- Có keyword `data`, `privacy`, `gdpr`, `dữ liệu`, `rò rỉ` -> gọi `privacy_agent`.
- Nếu không có specialist phù hợp -> đi thẳng `aggregate_results`.

### Bài tập 5.1 - Trace request flow

Luồng Stage 5:

```text
User/test_client.py
  -> Customer Agent :10100
  -> Registry discover legal_question :10000
  -> Law Agent :10101
  -> Registry discover tax_question/compliance_question
  -> Tax Agent :10102 và Compliance Agent :10103 chạy song song
  -> Law Agent aggregate
  -> Customer Agent
  -> User/test_client.py
```

Trong logs có `trace_id` và `context_id` để theo dõi cùng một request qua nhiều agent.

### Bài tập 5.2 - Test dynamic discovery

Khi dừng Tax Agent rồi chạy lại `test_client.py`:

- Law Agent vẫn discover Tax Agent qua Registry.
- Nếu endpoint không phản hồi, `call_tax` bắt exception.
- Hệ thống trả về thông báo dạng `Tax analysis unavailable` thay vì crash toàn bộ flow.

### Bài tập 5.3 - Modify agent behavior

Có thể sửa prompt trong `tax_agent/graph.py` để Tax Agent trả lời ngắn hơn.

Ví dụ thêm yêu cầu:

```text
Trả lời ngắn gọn, dưới 120 từ, ưu tiên bullet points.
```

Sau đó restart Tax Agent và chạy lại `test_client.py`.

## 2. Câu hỏi ôn tập

### Khi nào nên dùng single agent thay vì multi-agent?

Dùng single agent khi bài toán đơn giản, ít domain, không cần scale từng phần độc lập và muốn giảm độ phức tạp/latency.

### Ưu điểm của A2A so với REST/gRPC thông thường?

A2A có chuẩn agent card, task/message/artifact, trace/context metadata và discovery theo capability. REST/gRPC chỉ là giao tiếp service tổng quát, không có semantic riêng cho agent.

### Làm sao tránh infinite delegation loops?

- Truyền `delegation_depth`.
- Tăng depth sau mỗi lần delegate.
- Dừng khi đạt `MAX_DELEGATION_DEPTH`.
- Theo dõi `trace_id`.
- Có thể bổ sung visited-agents và timeout/retry limit.

### Tại sao cần Registry service?

Registry giúp agent tự đăng ký capability và discover endpoint theo task. Có thể hardcode URL trong demo nhỏ, nhưng không phù hợp hệ distributed vì khó scale, khó đổi port/host và tăng coupling.

## 3. Bài tập cộng điểm

### HTML demo tương tác agent

Đã tạo:

```text
docs/agent_interaction.html
```

HTML này demo luồng Stage 5 và optimized flow, có trace, latency, lệnh chạy thật.

### Latency Stage 5

Sau khi chạy full Stage 5 với API key mới:

```text
TOTAL_LATENCY_SECONDS=427.49
```

Optimized mode:

```text
AVERAGE_LATENCY_SECONDS=386.48
```

Giảm được:

```text
427.49 - 386.48 = 41.01 giây
```

Tương đương khoảng `9.59%`.

Phương án giảm latency đã áp dụng:

- Thay LLM router ở Law Agent bằng keyword routing khi bật `LATENCY_OPTIMIZED=1`.
- Bỏ final synthesis LLM call trong Law Agent ở optimized mode.
- Tăng `A2A_TIMEOUT_SECONDS` để full Stage 5 không timeout khi model trả chậm.
- Có thể giảm `OPENROUTER_MAX_TOKENS` khi demo để tránh output quá dài.

## 4. Assignment Day08 Supervisor - Workers

Đã tạo folder:

```text
Lab_Assignment/
```

Nội dung:

- `supervisor_workers.py`: Supervisor và 3 workers.
- `run_demo.py`: CLI demo.
- `app.py`: FastAPI API.
- `static/index.html`: giao diện web demo.
- `README.md`: hướng dẫn chạy.

Pattern:

```text
User question
  -> Supervisor
  -> LegalWorker / NewsWorker / ConversationWorker
  -> Supervisor synthesize answer
  -> answer + trace + latency + evidence
```

Chạy CLI:

```bash
uv run python Lab_Assignment/run_demo.py
```

Chạy web:

```bash
uv run uvicorn Lab_Assignment.app:app --host 127.0.0.1 --port 8510
```

