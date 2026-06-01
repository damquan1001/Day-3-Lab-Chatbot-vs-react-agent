# System Flowchart: Chatbot vs ReAct Agent

Biểu đồ dưới đây miêu tả luồng hoạt động của hệ thống, so sánh giữa **Baseline Chatbot** (được cung cấp toàn bộ dữ liệu từ đầu) và **ReAct Agent** (hoạt động theo tư duy vòng lặp và dùng Tools).

```mermaid
graph TD
    User([Người dùng]) --> API[API Server]

    API --> |Chọn chế độ| Router{Chatbot hay Agent?}

    %% --- Nhánh Baseline Chatbot ---
    Router -->|Baseline| BaseLoad[Load toàn bộ file banggia.xlsx thành CSV string]
    BaseLoad --> BasePrompt[Đưa Full CSV vào System Prompt]
    BasePrompt --> BaseLLM((LLM: Gemini / GPT))
    BaseLLM --> BaseAns[Đọc CSV và sinh ra câu trả lời trực tiếp]
    BaseAns --> Return1([Trả kết quả cho người dùng])

    %% --- Nhánh ReAct Agent ---
    Router -->|ReAct Agent| AgentInit[Khởi tạo Agent với max_steps = 5]
    AgentInit --> AgentLoop((Vòng lặp ReAct))

    subgraph "ReAct Loop (Tối đa 5 bước)"
        AgentLoop --> LLM_Think[LLM suy nghĩ: 'Thought']
        
        LLM_Think --> |Cần gọi Tool| Action[LLM chọn 'Action: Tên Tool']
        Action --> ToolExec[Thực thi Tool với tham số JSON]
        
        ToolExec --> |1. search_products<br/>2. get_product_price<br/>3. compare_products<br/>4. calculate_cart_total| ToolOutput[Trả về kết quả (Observation)]
        ToolOutput --> LLM_Think
        
        LLM_Think --> |Đủ thông tin / Lọc xong| FinalAns[LLM chọn 'Final Answer']
    end

    FinalAns --> CheckThin{Kiểm tra Final Answer<br/>có quá ngắn?}
    
    CheckThin -->|Có (Thin Answer)| Rewrite[Rewrite Prompt: Ép liệt kê tất cả kết quả và viết dài ra]
    Rewrite --> Return2([Trả kết quả cho người dùng])
    
    CheckThin -->|Không| Return2
    Return1 --> UI[Frontend / Giao diện hiển thị]
    Return2 --> UI
```

### Giải thích các thành phần:

1. **Baseline Chatbot (Bên trái):** Nạp tĩnh (static) toàn bộ file Excel vào trong Prompt của LLM. Mặc dù giúp LLM có cái nhìn toàn cảnh, nhưng sẽ rất tốn kém Tokens và gặp giới hạn nếu Database lên tới hàng vạn dòng.
2. **ReAct Agent (Bên phải):** 
   - Không nạp sẵn Database. Thay vào đó nó nhận được một bộ danh sách các **Tools** (công cụ).
   - Nó chạy theo một vòng lặp: Suy nghĩ xem nên làm gì (**Thought**) -> Dùng công cụ nào (**Action**) -> Đọc kết quả từ công cụ trả về (**Observation**).
   - Vì Tool chỉ trả về giới hạn số lượng kết quả (`max_results = 20-50`), nên Agent đã được thiết lập thêm một bước **CheckThin** để ép nó không được kết luận vội vàng mà phải đọc kỹ Observation, liệt kê ra toàn bộ lựa chọn trước khi đưa ra `Final Answer`.
