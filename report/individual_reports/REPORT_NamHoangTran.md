# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nam Hoang
- **Student ID**: 2A202600870
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

*Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.).*

- **Modules Implementated**: `src/agent/agent.py` và `src/tools/catalog_tools.py`
- **Code Highlights**: 
  - Đã cập nhật `get_system_prompt()` trong `agent.py` để bổ sung yêu cầu: "You MUST first summarize or list all the available options/products found from your search/filter (the full data)."
  - Tăng điều kiện bắt buộc chiều dài của `_final_answer_is_too_thin` lên 400 ký tự và ép ít nhất 4 ý (câu/gạch đầu dòng).
  - Tăng giới hạn trả về của Tool `search_products` và `compare_products` từ `max_results = 5` lên `20` (max = 50) trong file `catalog_tools.py`.
- **Documentation**: Sửa đổi logic của ReAct Agent để nó không bỏ qua các dữ liệu lấy được từ Tool, ép nó phải hoạt động phân tích giống như một tư vấn viên thay vì chọn bừa một đáp án ngắn gọn.

---

## II. Debugging Case Study (10 Points)

*Analyze a specific failure event you encountered during the lab using the logging system.*

- **Problem Description**: ReAct Agent trả về kết quả quá ngắn gọn bằng tiếng Anh ("The AKKO 3098B Plus at PhongVu is a good wireless keyboard option...") mà không hề so sánh với các sản phẩm khác, phớt lờ hoàn toàn yêu cầu trả lời tiếng Việt.
- **Log Source**: `logs/2026-06-01.log` hoặc trace in ra từ `api_server.py`.
- **Diagnosis**: 
  1. Do Tool trả về quá ít data (mặc định chỉ 5 kết quả).
  2. Do Agent model sinh câu trả lời bị "lười", và hàm `_final_answer_is_too_thin()` kiểm tra < 220 ký tự chưa đủ chặt chẽ để chặn câu trả lời 157 ký tự bằng tiếng Anh. Khi hàm rewrite thất bại nó sẽ trượt thẳng ra kết quả cuối.
- **Solution**: Đã nâng cấp `_final_answer_is_too_thin()` kiểm tra lên `len < 400`, đồng thời ép `sentence_count < 4`. Kèm theo việc mở rộng size observation từ Tools để LLM không bị thiếu data.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflect on the reasoning capability difference.*

1.  **Reasoning**: `Thought` block giúp Agent suy nghĩ từng bước, gọi Tool tìm kiếm, phân tích dữ liệu trả về trước khi đưa ra kết luận. Khác với Chatbot bị ngợp bởi một núi Data CSV đập thẳng vào mặt, Agent có khả năng tự chắt lọc thông tin nhờ các tool query.
2.  **Reliability**: Trong các câu hỏi cần quét toàn bộ kho để tìm sản phẩm *độc lạ* mà chưa biết keyword chính xác, Agent có thể tệ hơn Chatbot vì Tool Search bị giới hạn từ khoá và số lượng kết quả (nếu keyword không match, Tool sẽ không trả về gì). Trong khi Chatbot có Full CSV nên nó tự tự "tìm thủ công" bằng mắt của LLM.
3.  **Observation**: Observation là mạch máu của ReAct. Nếu Observation cụt ngủn hoặc rỗng, Agent sẽ hoang mang, tự bịa ra dữ liệu (hallucinate) hoặc trả về lỗi cụt lủn. Việc mở rộng data trả về cho Observation đã quyết định 90% chất lượng của Final Answer.

---

## IV. Future Improvements (5 Points)

*How would you scale this for a production-level AI agent system?*

- **Scalability**: Thay vì viết Tool đọc file excel thủ công bằng python cơ bản, nên tích hợp với Vector Database hoặc Elasticsearch để có khả năng search Semantic thay vì Exact Match.
- **Safety**: Xây dựng một Guardrail Agent chạy song song chuyên kiểm duyệt câu trả lời (Final Answer) của ReAct Agent để chặn việc nó lười biếng hoặc văng tiếng Anh trước khi gửi cho End-User.
- **Performance**: Xử lý async (bất đồng bộ) khi gọi nhiều tool song song thay vì tuần tự, rút ngắn độ trễ (hiện tại mất gần 10s cho 2-3 step).
