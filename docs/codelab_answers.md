# Trả lời câu hỏi CODELAB Day09

## Câu hỏi ôn tập

### 1. Khi nào nên dùng single agent thay vì multi-agent?

Nên dùng single agent khi bài toán còn đơn giản, phạm vi hẹp, không cần chia chuyên môn cho nhiều domain khác nhau và không cần scale từng phần độc lập. Ví dụ: một chatbot hỏi đáp cơ bản, một agent có vài tool để tra cứu hoặc tính toán, hoặc workflow ngắn mà một LLM có thể tự xử lý tốt.

Single agent phù hợp khi:

- Câu hỏi không cần nhiều chuyên gia khác nhau.
- Không cần xử lý song song nhiều nhánh.
- Muốn kiến trúc đơn giản, dễ debug, dễ deploy.
- Latency và chi phí cần thấp hơn vì ít lượt gọi LLM/HTTP hơn.

Multi-agent nên dùng khi bài toán có nhiều domain chuyên biệt, ví dụ hệ thống pháp lý cần Law Agent, Tax Agent, Compliance Agent; hoặc khi muốn mỗi agent có trách nhiệm riêng và có thể scale/fail độc lập.

### 2. Ưu điểm của A2A protocol so với gRPC hoặc REST thông thường?

A2A được thiết kế riêng cho giao tiếp giữa các AI agent, nên ngoài HTTP request/response thông thường, nó có thêm khái niệm phù hợp với agent như Agent Card, task/message/artifact, capability discovery, context_id và trace_id.

Ưu điểm chính:

- Agent có thể tự mô tả năng lực qua `/.well-known/agent.json` hoặc agent card.
- Các agent có thể discover nhau theo task/capability thay vì gọi endpoint hardcode.
- Dễ truyền ngữ cảnh hội thoại, trace_id, context_id giữa nhiều agent.
- Hỗ trợ mô hình distributed multi-agent tốt hơn REST thuần vì REST chỉ định nghĩa endpoint, không định nghĩa chuẩn agent/task/message.
- Linh hoạt hơn gRPC trong demo/học tập vì chạy qua HTTP/JSON, dễ inspect logs và dễ tích hợp với nhiều service khác nhau.

REST/gRPC vẫn tốt cho microservice truyền thống, nhưng A2A phù hợp hơn khi các service là AI agents cần tự mô tả, phối hợp và trao đổi task.

### 3. Làm thế nào để prevent infinite delegation loops trong A2A?

Cần giới hạn độ sâu delegation và truyền metadata qua mỗi lần agent gọi agent khác. Trong code Day09, hệ thống dùng `delegation_depth` và `MAX_DELEGATION_DEPTH = 3` trong Law Agent.

Cách phòng tránh:

- Mỗi request mang theo `delegation_depth`.
- Mỗi lần delegate sang agent khác thì tăng depth thêm 1.
- Nếu depth đạt `MAX_DELEGATION_DEPTH`, agent không gọi tiếp sub-agent nữa.
- Dùng `trace_id` để theo dõi toàn bộ vòng đời request trong logs.
- Có thể bổ sung visited-agents list để tránh agent A gọi B, rồi B gọi ngược A vô hạn.
- Đặt timeout/retry limit cho mỗi A2A call.

Nhờ vậy hệ thống không bị lặp vô hạn khi agent routing sai hoặc các agent gọi vòng nhau.

### 4. Tại sao cần Registry service? Có thể hardcode URLs không?

Registry service cần để các agent đăng ký capability khi khởi động và các agent khác có thể tìm endpoint theo task, ví dụ `legal_question`, `tax_question`, `compliance_question`.

Lợi ích của Registry:

- Không cần hardcode URL của từng agent trong code gọi.
- Khi đổi port, đổi host, scale agent hoặc deploy sang máy khác, chỉ cần agent register lại.
- Hỗ trợ dynamic discovery: Customer Agent tìm Law Agent, Law Agent tìm Tax/Compliance Agent theo capability.
- Làm kiến trúc giống production hơn, dễ mở rộng thêm agent mới.
- Giảm coupling giữa các service.

Có thể hardcode URLs trong demo nhỏ, nhưng không nên cho hệ thống distributed thật vì khó bảo trì, khó scale và dễ lỗi khi endpoint thay đổi.

## Bài tập cộng điểm

### 1. HTML file demo tương tác giữa các Agent Stage 4 hoặc Stage 5

Đã làm file demo tại:

```bash
docs/agent_interaction.html
```

File này là HTML self-contained, mở trực tiếp bằng browser. Nội dung demo Stage 5 gồm các thành phần:

- Registry Service `:10000`
- Customer Agent `:10100`
- Law Agent `:10101`
- Tax Agent `:10102`
- Compliance Agent `:10103`
- Luồng User/test_client.py gửi câu hỏi vào Customer Agent
- Customer Agent discover Law Agent qua Registry
- Law Agent phân tích, routing, rồi gọi Tax Agent và Compliance Agent song song qua A2A
- Law Agent aggregate kết quả và trả về Customer Agent/User
- Có nút `Play Stage 5` và `Play Optimized` để minh họa cả luồng đầy đủ và luồng tối ưu latency

### 2. Latency tổng thời gian trả lời 1 câu hỏi của hệ thống là bao nhiêu giây?

Đã đo bằng `benchmark_latency.py` sau khi chạy full Stage 5.

Kết quả baseline:

```text
TOTAL_LATENCY_SECONDS=427.49
```

Vậy latency tổng cho một câu hỏi trong lần đo này là khoảng **427.49 giây**.

Ghi chú: đây là lần đo full Stage 5 sau khi thay API key mới, model hiện tại là `openai/gpt-oss-120b:free`, chạy với `A2A_TIMEOUT_SECONDS=600` và runtime `OPENROUTER_MAX_TOKENS=512` để tránh timeout khi các agent specialist trả lời rất dài.

### 3. Đề xuất phương án giảm latency và demo/show thời gian xử lý đã giảm được khi apply phương án?

Phương án đã apply trong code là bật chế độ:

```bash
LATENCY_OPTIMIZED=1
```

Cụ thể đã tối ưu trong `law_agent/graph.py`:

1. Thay LLM routing ở Law Agent bằng keyword routing deterministic.
2. Bỏ final synthesis LLM call ở Law Agent trong demo optimized mode.
3. Vẫn giữ kiến trúc distributed A2A: Registry, Customer Agent, Law Agent, Tax Agent, Compliance Agent vẫn chạy độc lập và giao tiếp qua HTTP/A2A.
4. Tax Agent và Compliance Agent vẫn được gọi song song bằng LangGraph `Send` API.

Kết quả đo sau tối ưu:

```text
AVERAGE_LATENCY_SECONDS=386.48
```

So sánh:

| Mode | Latency |
|---|---:|
| Baseline Stage 5 | 427.49s |
| Optimized Stage 5 | 386.48s |
| Giảm được | 41.01s |
| Tỷ lệ giảm | khoảng 9.59% |

Kết luận: Sau khi apply phương án tối ưu, thời gian xử lý giảm từ **427.49 giây** xuống **386.48 giây**, giảm **41.01 giây** tương đương khoảng **9.59%** trong lần đo này.

Các hướng tối ưu thêm nếu triển khai production:

- Cache Registry discovery và Agent Card để giảm HTTP round-trip lặp lại.
- Reuse HTTP client thay vì tạo client mới nhiều lần.
- Dùng model nhanh/rẻ hơn cho routing và summarization, model mạnh hơn cho phân tích chính.
- Giảm `OPENROUTER_MAX_TOKENS` theo nhu cầu thực tế.
- Streaming response để người dùng thấy câu trả lời sớm hơn dù toàn bộ workflow chưa kết thúc.
- Thêm retry/backoff thông minh để tránh chờ lâu khi provider lỗi.
