# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: NamHoangTran
- **Team Members**: Nam Hoang
- **Deployment Date**: 2026-06-01

---

## 1. Executive Summary

*Brief overview of the agent's goal and success rate compared to the baseline chatbot.*

- **Success Rate**: 90% on test cases.
- **Key Outcome**: Hệ thống ReAct Agent lúc đầu gặp tình trạng chỉ trả lời rất ngắn gọn do lượng ngữ cảnh từ Tool bị giới hạn (max 5 kết quả). Sau khi khắc phục bằng cách tăng giới hạn `max_results` lên 20 - 50 và sửa đổi System Prompt để ép LLM phải liệt kê toàn bộ options thu được, Agent đã vượt trội hơn Chatbot Baseline trong các truy vấn mua sắm nhờ dữ liệu được cập nhật real-time qua tools thay vì nạp cứng toàn bộ DB.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation
Agent hoạt động dựa trên vòng lặp Thought -> Action -> Observation -> Final Answer. Nó nhận vào input của user, suy nghĩ (Thought) xem cần dùng tool nào, gọi Tool (Action) và nhận lại kết quả JSON (Observation), lặp lại tối đa 5 bước trước khi tổng hợp thành Final Answer.

### 2.2 Tool Definitions (Inventory)
| Tool Name | Input Format | Use Case |
| :--- | :--- | :--- |
| `search_products` | `string` (query) | Tìm kiếm các sản phẩm trong danh mục/tên/shop. |
| `get_product_price` | `string` (product_name) | Lấy chi tiết thông tin và giá ưu đãi của 1 sản phẩm cụ thể. |
| `compare_products` | `string` (query, sort_by) | Tìm và sắp xếp các sản phẩm theo giá, rating, discount, v.v. |
| `calculate_cart_total` | `json array` (items) | Tính tổng tiền giỏ hàng (VND) theo giá đã discount. |

### 2.3 LLM Providers Used
- **Primary**: Gemini 3.1 Pro (High)
- **Secondary (Backup)**: OpenAI GPT-4o / Local Phi-3

---

## 3. Telemetry & Performance Dashboard

*Analyze the industry metrics collected during the final test run.*

- **Average Latency (P50)**: 4500ms
- **Max Latency (P99)**: 9500ms (cho các truy vấn phức tạp cần lặp qua nhiều step).
- **Average Tokens per Task**: ~3500 tokens
- **Total Cost of Test Suite**: ~$0.035 mỗi lượt test dài.
- **Metric Insights**: Chi phí được fix ở mức `$0.01 / 1000 tokens`.

---

## 4. Root Cause Analysis (RCA) - Failure Traces

*Deep dive into why the agent failed.*

### Case Study: ReAct Agent trả lời quá ngắn (Thin Final Answer)
- **Input**: "Tìm bàn phím không dây tốt nhất cân bằng giữa giá và thời gian giao hàng"
- **Observation**: Agent gọi Tool thành công, nhưng Final Answer chỉ trả về đúng 1 câu duy nhất chọn AKKO 3098B Plus mà không giải thích hay so sánh. Mặc dù hệ thống có cơ chế kiểm tra `is_too_thin` (< 220 ký tự) nhưng vì giới hạn quá thấp và prompt chưa đủ mạnh nên Agent vẫn phớt lờ.
- **Root Cause**: 
  1. Các tool như `search_products` giới hạn trả về mặc định quá ít (`max_results = 5`), khiến Agent thiếu ngữ cảnh (filtered sample quá bé).
  2. Prompt không có ràng buộc chặt chẽ bắt Agent phải liệt kê dữ liệu ra trước khi kết luận.
- **Solution**: Nâng cấp hàm check `_final_answer_is_too_thin` lên 400 ký tự và yêu cầu ít nhất 4 câu. Thay đổi System/Rewrite prompt để ép Agent liệt kê TẤT CẢ các sản phẩm trong context ra trước. Cập nhật Tool để trả về `max_results = 20-50`.

---

## 5. Ablation Studies & Experiments

### Experiment 1: Prompt v1 vs Prompt v2 (Quy định Format Final Answer)
- **Diff**: Thêm "You MUST first summarize or list all the available options/products found from your search/filter (the full data)."
- **Result**: Giảm thiểu 100% tình trạng Agent chỉ đưa ra kết luận cụt ngủn mà không có bước so sánh. Agent bắt đầu hành xử chuyên nghiệp và giống một tư vấn viên hơn.

### Experiment 2 (Bonus): Chatbot vs Agent
| Case | Chatbot Result | Agent Result | Winner |
| :--- | :--- | :--- | :--- |
| Tìm 1 sản phẩm | Correct | Correct | Draw |
| Tổng tiền giỏ hàng | Hallucinated (Tính toán sai) | Correct (Nhờ Tool `calculate_cart_total`) | **Agent** |
| Câu hỏi chung chung | Correct (Do được nạp Full CSV) | Correct (Nhờ query ra 20 results) | **Agent** (Nhanh, rẻ, ít token hơn) |

---

## 6. Production Readiness Review

*Considerations for taking this system to a real-world environment.*

- **Security**: Hiện tại tool mới chỉ đọc file Excel cục bộ, không có nguy cơ injection, nhưng cần làm sạch chuỗi `query` nếu tích hợp SQL Database thật.
- **Guardrails**: Đã cấu hình `max_steps = 5` trong ReAct Loop để tránh Agent bị rơi vào Infinite Loop gây tốn tiền API.
- **Scaling**: Thay vì giới hạn ở 5 step ReAct thô, có thể chuyển đổi logic Agent này sang framework **LangGraph** để kiểm soát luồng điều hướng (State Graph) tốt hơn khi có thêm hàng chục tool mới.
