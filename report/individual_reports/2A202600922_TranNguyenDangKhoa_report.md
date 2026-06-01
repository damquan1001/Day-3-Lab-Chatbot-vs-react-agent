# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Trần Nguyễn Đăng Khoa
- **Student ID**: 2A202600922
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

Phần đóng góp chính của em tập trung vào **scope guardrails**, **system prompt engineering** cho cả baseline và ReAct agent, **cải thiện trải nghiệm user-facing** (không lộ nguồn dữ liệu nội bộ), và **tài liệu hướng dẫn chạy project** cho team trên Windows.

### Modules Implemented / Modified

| Module | Vai trò |
|---|---|
| `src/agent/guards.py` | Message guard (greeting / out-of-scope / safety), `SCOPE_SAFETY_PROMPT` dùng chung, keyword out-of-scope, chuẩn hóa tiếng Việt (`đ` → `d`) |
| `src/agent/agent.py` | Cập nhật `get_system_prompt()` — domain sản phẩm công nghệ; rule không nhắc file/path trong Final Answer; prompt rewrite |
| `src/chat/baseline.py` | `SYSTEM_PROMPT` baseline tech shopping; đổi header catalog trong `build_prompt()` |
| `src/database/loader.py` | `build_system_prompt()` — mô tả domain công nghệ, cấm lộ nguồn dữ liệu |
| `frontend/src/components/AppShell.tsx` | UI sidebar: thay nhãn `banggia.xlsx` bằng mô tả user-friendly |
| `docs/RUN.md` | Hướng dẫn setup & chạy local (venv, `.env`, backend, frontend, troubleshooting) |
| `tests/test_agent.py` | Test guard out-of-scope cho câu *"nhiệt độ Hà Nội"* |

### Code Highlights

**1. Shared scope block — agent và baseline dùng chung `SCOPE_SAFETY_PROMPT`:**

```python
# src/agent/guards.py
SCOPE_SAFETY_PROMPT = """
Scope and safety:
- You are a tech shopping assistant for Lab 3: mice, keyboards, monitors, laptops, headphones, webcams, and similar gear.
- This catalog does NOT contain clothing, food, or general household items — never suggest those.
- NEVER mention file names, paths, spreadsheets, databases, or lab internals in user-facing text ...
"""
```

**2. ReAct agent — domain + rule Final Answer (`src/agent/agent.py`):**

```python
You are a ReAct shopping agent for Lab 3.
You specialize in tech/IT products: mice, keyboards, monitors, laptops, headphones, webcams, and similar gear.
This catalog does NOT contain clothing, food, or general household items — never suggest those.
...
- Final Answer is user-facing: never mention file names, paths, spreadsheets, databases, or tool names.
```

**3. Input guard chặn sớm — không gọi LLM khi out-of-scope (`ReActAgent.run`):**

```python
guarded = check_input_guards(user_input)
if guarded:
    logger.log_event("OUT_OF_SCOPE", {...})
    return guarded  # canned message tiếng Việt, 0 bước ReAct
```

**4. Chuẩn hóa tiếng Việt cho keyword matching:**

```python
# src/agent/guards.py — _normalize()
without_accents = without_accents.replace("đ", "d").replace("Đ", "d")
```

Trước khi sửa, câu *"nhiệt độ Hà Nội"* không khớp keyword `nhiet do` vì ký tự `đ` không được chuyển thành `d`.

### Documentation — Tương tác với ReAct loop

- **`check_input_guards`** chạy **trước** vòng lặp Thought → Action → Observation. Câu hỏi ngoài phạm vi (thời tiết, tin tức…) trả canned reply ngay, log `OUT_OF_SCOPE`, `AGENT_END` với `steps: 0` — tiết kiệm token và tránh hallucination.
- **`SCOPE_SAFETY_PROMPT`** được inject vào system prompt mỗi bước LLM, hướng agent chỉ tư vấn sản phẩm công nghệ từ tool observations.
- **Baseline** dùng cùng block scope qua `SYSTEM_PROMPT`, đảm bảo hành vi nhất quán khi so sánh qua `/api/compare`.
- **`docs/RUN.md`**: hướng dẫn team activate `.venv`, cấu hình provider, chạy `api_server.py` + frontend, đọc `logs/` cho debugging.

---

## II. Debugging Case Study (10 Points)

### Problem Description

Khi test trên UI (`POST /api/compare`) với câu hỏi **"nhiệt độ Hà Nội"**:

1. **Baseline Chatbot** từ chối đúng hướng nhưng vẫn nhắc *"catalog banggia.xlsx"* — lộ implementation detail cho end-user.
2. **ReAct Agent (v2)** chạy **3 bước**, ~7.4s latency, ~2772 tokens — rồi **gợi ý sai domain**: áo khoác, găng tay, khăn choàng thay vì từ chối hoặc redirect sang sản phẩm công nghệ.

Đây là lỗi **hallucination + scope drift**: model cố "giúp" user bằng kiến thức thế giới ngoài catalog.

### Log Source

Sau khi chạy test suite, log cho thấy flow ReAct đúng khi guard hoạt động:

```json
{"event": "OUT_OF_SCOPE", "data": {"input_length": 16, "version": 2}}
{"event": "AGENT_END", "data": {"steps": 0, "status": "out_of_scope"}}
```

Và flow thành công khi câu hỏi in-scope (`logs/2026-06-01.log`):

```json
{"event": "AGENT_START", "data": {"input": "tim ban phim", "tools": ["search_products"], "version": 1}}
{"event": "AGENT_STEP", "data": {"step": 1, "llm_preview": "Thought: Need catalog lookup.\nAction: search_products(...)"}}
{"event": "AGENT_TOOL_CALL", "data": {"tool": "search_products", "observation_preview": "{\"products\": [{\"product_name\": \"DareU EK87\", ...}]}"}}
{"event": "AGENT_END", "data": {"steps": 2, "status": "final"}}
```

Trước fix, câu *"nhiệt độ"* không sinh event `OUT_OF_SCOPE` — agent vào `AGENT_START` và LLM tự bịa câu trả lời.

### Diagnosis

| Nguyên nhân | Chi tiết |
|---|---|
| **System prompt quá chung** | Chỉ nói "catalog" / "banggia.xlsx", không mô tả domain **công nghệ** → LLM mặc định gợi ý quần áo cho câu hỏi thời tiết |
| **Guard thiếu keyword** | `_OUT_OF_SCOPE_KEYWORDS` có `thời tiết` nhưng thiếu `nhiệt độ` / `temperature` |
| **Bug chuẩn hóa tiếng Việt** | `_normalize()` strip dấu NFD nhưng không map `đ` → `d`, nên `"nhiệt độ"` không match `"nhiet do"` |
| **User-facing messages** | `OUT_OF_SCOPE_MESSAGE_VI` và `GREETING_HINT_VI` hardcode tên file |

Không phải lỗi tool spec hay parser — là **prompt + guard layer**.

### Solution

1. **`SCOPE_SAFETY_PROMPT`**: domain tech-only; cấm gợi ý quần áo; cấm nhắc file/path trong câu trả lời user.
2. **`get_system_prompt()` / `SYSTEM_PROMPT`**: mô tả rõ chuột, bàn phím, màn hình, laptop…
3. **Guard messages** (`OUT_OF_SCOPE`, `GREETING`): tiếng Việt tự nhiên, không nhắc `banggia.xlsx`.
4. **Thêm keyword** `nhiệt độ`, `nhiet do`, `temperature` vào `_OUT_OF_SCOPE_KEYWORDS`.
5. **Sửa `_normalize()`**: `đ/Đ` → `d`.
6. **Test** `test_v2_temperature_out_of_scope_does_not_call_llm` — xác nhận 0 LLM call.

Kết quả: câu *"nhiệt độ Hà Nội"* → từ chối ngắn gọn, hướng user hỏi sản phẩm công nghệ, **không tốn token ReAct loop**.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning — `Thought` block giúp gì so với Chatbot?

Với câu in-scope như *"tổng tiền 2 chuột rẻ nhất"*:

- **Chatbot** phải nhìn toàn bộ CSV catalog trong prompt và tự suy luận nhiều bước trong một lần generate — dễ sai số hoặc bỏ sót sản phẩm khi catalog lớn.
- **ReAct Agent** tách reasoning thành từng bước có log:
  - `Thought`: hiểu cần search + tính tổng
  - `Action: search_products(...)` → `Observation`: JSON thật từ DB
  - `Thought`: đủ dữ liệu → `Final Answer`

`Thought` giúp **debug được** agent đang nghĩ gì trước khi gọi tool — baseline không có layer này nên khi sai chỉ thấy câu trả lời cuối, không biết model "nghĩ" thế nào.

### 2. Reliability — Agent kém hơn Chatbot khi nào?

Em quan sát agent **kém hơn** trong các trường hợp:

| Tình huống | Vì sao agent kém hơn |
|---|---|
| Câu hỏi đơn giản, 1 fact | Baseline trả lời 1 bước; agent tốn 2–3 LLM calls + parse overhead |
| Câu out-of-scope (trước fix) | Agent vẫn chạy loop và hallucinate; baseline từ chối sớm hơn |
| Model local (Phi-3 CPU) | Parser ReAct hay lỗi format `Action:` → `AGENT_PARSE_ERROR`, cần retry |
| Final Answer quá ngắn | Agent phải rewrite thêm 1 LLM call (`AGENT_FINAL_TOO_THIN`) |

**Kết luận:** Agent không phải lúc nào cũng "thông minh hơn" — cần guard + version v2 để không tệ hơn chatbot trên câu ngoài phạm vi.

### 3. Observation — Feedback ảnh hưởng bước tiếp theo thế nào?

Observation là **ground truth** từ tool, không phải suy đoán LLM:

- Observation rỗng (`products: []`) → bước sau agent đổi query hoặc giải thích không tìm thấy.
- v2 **catalog tool gate**: nếu user hỏi giá/so sánh mà agent nhảy `Final Answer` không gọi tool → Observation bắt buộc: *"You must call at least one catalog tool..."* — ép agent quay lại Action.
- Duplicate action bị chặn → Observation *"Duplicate action blocked"* → tránh loop vô ích.

Đây là khác biệt cốt lõi với chatbot: **môi trường phản hồi có cấu trúc** thay vì model tự tin vào memory.

---

## IV. Future Improvements (5 Points)

### Scalability

- Tách **tool registry** động: khi có >10 tools, dùng embedding retrieval chọn subset tool đưa vào prompt (tránh context quá dài).
- Queue bất đồng bộ cho tool I/O (search catalog, gọi API ngoài) — ReAct loop không block trên từng tool sync.
- Cache observation cho query lặp (dedup trong session).

### Safety

- **Supervisor LLM** (hoặc rule engine) audit `Action` trước khi execute — đặc biệt khi mở rộng tool write (đặt hàng, thanh toán).
- Mở rộng `check_input_guards` bằng classifier nhẹ thay vì chỉ keyword — bắt out-of-scope tinh hơn (*"nhiệt độ"*, *"có nên mua"* mixed intent).
- Rate limit theo session + cap token/ngày trên `PerformanceTracker`.

### Performance

- **RAG** trên catalog: embed mô tả sản phẩm, tool `search_products` gọi vector DB thay vì scan full XLSX mỗi lần.
- Prompt compression: không paste full CSV vào baseline khi catalog > N dòng — baseline chuyển sang retrieve top-k.
- Default `AGENT_VERSION=2` + guard pre-LLM cho mọi path (chat stream, compare) để giảm token lãng phí.
- Cost tracking thật trong `metrics._calculate_cost()` theo bảng giá OpenAI/Gemini thay vì mock.

---

> Báo cáo nộp theo template Lab 3 — `report/individual_reports/2A202600922_TranNguyenDangKhoa_report.md`
