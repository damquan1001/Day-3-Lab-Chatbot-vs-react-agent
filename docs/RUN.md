# Hướng dẫn chạy Lab 3 — Chatbot vs ReAct Agent

Tài liệu này hướng dẫn setup và chạy project trên **Windows** (PowerShell).  
Stack: **Python (FastAPI)** backend + **React (Vite)** frontend.

---

## 1. Yêu cầu hệ thống

| Thành phần | Phiên bản khuyến nghị |
|---|---|
| Python | 3.10+ (3.12 OK) |
| Node.js | LTS v20/v22 (cho frontend) |
| RAM | ≥ 8GB (nếu chạy model local CPU) |
| Disk | ~3GB (model GGUF ~2.2GB) |

---

## 2. Clone & cấu trúc thư mục

```powershell
cd D:\AI20K\day3\team\Day-3-Lab-Chatbot-vs-react-agent
```

Các thư mục/file quan trọng:

```
.
├── api_server.py          # Backend API (port 3003)
├── chatbot.py             # Chatbot CLI (terminal)
├── requirements.txt
├── .env.example           # Template cấu hình
├── models/                # Model GGUF (tự tạo, gitignore)
├── src/database/banggia.xlsx   # Catalog sản phẩm (bắt buộc)
├── src/agent/agent.py     # ReAct agent v1/v2
├── frontend/              # UI React
└── logs/                  # Telemetry JSON (tự tạo khi chạy)
```

> **Lưu ý:** `banggia.xlsx` phải có tại `src/database/banggia.xlsx`. Thiếu file này → API/agent sẽ lỗi khi load catalog.

---

## 3. Setup Python (backend)

### 3.1 Tạo & kích hoạt virtual env

```powershell
cd D:\AI20K\day3\team\Day-3-Lab-Chatbot-vs-react-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Nếu bị chặn execution policy:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Prompt có `(.venv)` là đã activate đúng.

### 3.2 Cài dependencies

```powershell
pip install -r requirements.txt
```

> **Quan trọng:** Luôn dùng Python trong `.venv`. Không chạy `python api_server.py` bằng Python global (sẽ lỗi `No module named 'fastapi'` / `'dotenv'`).

Kiểm tra:

```powershell
python -c "import sys; print(sys.executable)"
# Kỳ vọng: ...\Day-3-Lab-Chatbot-vs-react-agent\.venv\Scripts\python.exe
```

Cách nhanh không cần activate:

```powershell
.\.venv\Scripts\python.exe api_server.py
```

---

## 4. Cấu hình `.env`

```powershell
copy .env.example .env
```

Chỉnh `.env` theo provider bạn dùng:

### Option A — Local model (CPU, không cần API key)

```env
DEFAULT_PROVIDER=local
DEFAULT_MODEL=Phi-3-mini-4k-instruct-q4
LOCAL_MODEL_PATH=./models/Phi-3-mini-4k-instruct-q4.gguf
AGENT_VERSION=2
```

Tải model:

- [Phi-3-mini-4k-instruct-GGUF](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf)
- Đặt file vào: `models/Phi-3-mini-4k-instruct-q4.gguf`

Lần load đầu có thể mất vài phút.

### Option B — OpenAI

```env
DEFAULT_PROVIDER=openai
OPENAI_API_KEY=sk-...
DEFAULT_MODEL=gpt-4o-mini
AGENT_VERSION=2
```

### Option C — Google Gemini

```env
DEFAULT_PROVIDER=google
GEMINI_API_KEY=...
DEFAULT_MODEL=gemini-1.5-flash
AGENT_VERSION=2
```

### Biến API / Frontend

```env
API_HOST=0.0.0.0
API_PORT=3003
VITE_API_BASE_URL=http://localhost:3003
```

---

## 5. Chạy Backend

**Terminal 1** (đã activate `.venv`):

```powershell
python api_server.py
```

Hoặc:

```powershell
uvicorn api_server:app --host 0.0.0.0 --port 3003
```

Kiểm tra:

- Health: http://localhost:3003/health
- Swagger: http://localhost:3003/docs

### API chính

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/chat` | Chat baseline (có session) |
| POST | `/api/compare` | So sánh Baseline vs ReAct |
| POST | `/api/chat/stream` | Streaming baseline |
| GET | `/api/telemetry` | Lấy telemetry events |
| GET | `/api/usage` | Token/latency summary |
| DELETE | `/api/session/{id}` | Xóa session |

Body mẫu `/api/compare`:

```json
{
  "message": "bàn phím nào rẻ nhất",
  "agent_version": 2
}
```

---

## 6. Chạy Frontend (UI)

**Terminal 2:**

```powershell
cd frontend
npm install
npm run dev
```

Mở UI: http://localhost:5173

> Backend phải chạy trước ở port **3003**.

### Nếu `node` / `npm` không nhận lệnh

1. Cài [Node.js LTS](https://nodejs.org)
2. **Đóng hẳn Cursor/terminal** rồi mở lại
3. Hoặc chạy tạm:

```powershell
& "C:\Program Files\nodejs\npm.cmd" install
& "C:\Program Files\nodejs\npm.cmd" run dev
```

---

## 7. Chạy Chatbot CLI (không cần UI)

```powershell
.\.venv\Scripts\Activate.ps1
python chatbot.py
python chatbot.py --provider openai
python chatbot.py --provider google
python chatbot.py --provider local
```

Gõ `quit` hoặc `exit` để thoát.

---

## 8. Chạy tests (tuỳ chọn)

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```

Tests dùng fake LLM — không cần model/API key thật.

---

## 9. Telemetry & logs

Mọi sự kiện agent ghi JSON vào:

```
logs/YYYY-MM-DD.log
```

Event thường gặp:

- `AGENT_START`, `AGENT_STEP`, `AGENT_TOOL_CALL`, `AGENT_END`
- `AGENT_PARSE_ERROR`, `AGENT_PARSE_RETRY`
- `OUT_OF_SCOPE`, `SAFETY_BLOCKED`
- `LLM_METRIC` (tokens, latency, cost estimate)

Dùng log này cho debugging và báo cáo lab (xem `SCORING.md`, `EVALUATION.md`).

---

## 10. Flow chạy đầy đủ (khuyến nghị)

```
Terminal 1:  .\.venv\Scripts\Activate.ps1  →  python api_server.py     → :3003
Terminal 2:  cd frontend  →  npm run dev                               → :5173
```

Trên UI: gửi câu hỏi → tab Compare xem **Baseline Chatbot** vs **ReAct Agent**.

---

## 11. Troubleshooting

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| `No module named 'fastapi'` / `'dotenv'` | Chưa dùng `.venv` | Activate venv hoặc `.\.venv\Scripts\python.exe api_server.py` |
| `node is not recognized` | Chưa cài Node hoặc chưa restart terminal | Cài Node LTS, restart IDE |
| `Local model not found` | Thiếu file GGUF | Tải model vào `models/` |
| `Price catalog not found` | Thiếu `banggia.xlsx` | Copy file vào `src/database/` |
| Frontend không gọi được API | Backend chưa chạy / sai port | Kiểm tra `:3003/health`, `VITE_API_BASE_URL` |
| Agent chậm | Model local trên CPU | Dùng OpenAI/Gemini hoặc giảm `max_steps` |

---

## 12. Agent version

| Version | Đặc điểm |
|---|---|
| **v1** | Parser legacy, Action phải kết thúc message |
| **v2** | Parser linh hoạt, parse retry, chặn duplicate action, bắt buộc gọi tool trước Final Answer, input guards |

Set trong `.env`:

```env
AGENT_VERSION=2
```

Hoặc gửi `"agent_version": 2` trong body `/api/compare`.

---

## 13. Chỉ chạy backend (không cần Node)

Nếu chưa cài Node.js, vẫn làm lab qua:

- `python chatbot.py` — baseline CLI
- `python api_server.py` + gọi API qua Postman/curl/`/docs`
- `pytest` — kiểm tra agent logic

---

*Tài liệu liên quan: [README.md](../README.md) · [SCORING.md](../SCORING.md) · [EVALUATION.md](../EVALUATION.md)*
