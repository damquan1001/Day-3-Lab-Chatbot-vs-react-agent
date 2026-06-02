# Setup and Run Guide

This guide explains how to set up and run the Lab 3 Chatbot vs ReAct Agent project.

The project has two main parts:

- **Backend**: Python FastAPI API on port `3003`
- **Frontend**: React + Vite UI on port `5173`

---

## 1. Requirements

Install these first:

- Python 3.10 or newer
- Node.js LTS
- Git

On Windows PowerShell, use `npm.cmd` if `npm` is blocked by execution policy.

---

## 2. Clone and Enter the Project

```powershell
git clone <your-repo-url>
cd Day-3-Lab-Chatbot-vs-react-agent
```

If you already have the project, just open a terminal in the project root.

---

## 3. Create the Python Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks virtualenv activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate again:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Windows note for `llama-cpp-python`

If `llama-cpp-python` is slow to build or fails on Windows, install the CPU wheel:

```powershell
python -m pip install llama-cpp-python --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --timeout 1000 --retries 10
```

---

## 4. Configure Environment Variables

Copy the example file:

```powershell
copy .env.example .env
```

Edit `.env` and fill in the provider you want to use.

### OpenAI

```env
DEFAULT_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
DEFAULT_MODEL=gpt-4o
```

### Gemini

```env
DEFAULT_PROVIDER=google
GEMINI_API_KEY=your_gemini_api_key_here
```

Supported Gemini models in the UI/backend are:

- `gemini-2.5-flash`
- `gemini-2.5-flash-lite`
- `gemini-3.1-flash-lite`

### Local GGUF model

```env
DEFAULT_PROVIDER=local
LOCAL_MODEL_PATH=./models/Phi-3-mini-4k-instruct-q4.gguf
```

Download a compatible `.gguf` model and place it in the `models/` folder.

### Backend and frontend ports

Keep these unless you need custom ports:

```env
API_HOST=0.0.0.0
API_PORT=3003
VITE_API_BASE_URL=http://localhost:3003
```

---

## 5. Run the Backend

From the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python api_server.py
```

The API should run at:

```text
http://localhost:3003
```

Check health:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:3003/health
```

You can also open:

```text
http://localhost:3003/docs
```

---

## 6. Run the Frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

If PowerShell blocks `npm`, use:

```powershell
npm.cmd install
npm.cmd run dev
```

Open the UI:

```text
http://localhost:5173
```

The UI lets you compare:

- Baseline Chatbot
- ReAct Agent

The response panels render Markdown, stream results as they complete, and save conversations in browser `localStorage`.

---

## 7. Main API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Backend health check |
| `POST` | `/api/chat` | Baseline chatbot response |
| `POST` | `/api/chat/stream` | Streaming baseline response |
| `POST` | `/api/compare` | Compare Baseline vs ReAct after both complete |
| `POST` | `/api/compare/stream` | Stream Baseline first, then ReAct |
| `GET` | `/api/telemetry` | View recent telemetry events |
| `GET` | `/api/usage` | Token, cost, and latency summary |
| `DELETE` | `/api/session/{session_id}` | Clear a backend session |

Example compare request:

```powershell
$payload = @{
  message = "Trả lời bằng tiếng Việt. Màn hình gaming nào rẻ nhất nhưng rating ít nhất 4.7 sao?"
  provider = "gemini"
  model = "gemini-2.5-flash"
} | ConvertTo-Json

Invoke-RestMethod http://localhost:3003/api/compare `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $payload
```

---

## 8. Run Tests

Backend tests:

```powershell
python -m pytest
```

Frontend tests:

```powershell
cd frontend
npm.cmd test
```

Frontend production build:

```powershell
cd frontend
npm.cmd run build
```

---

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | Activate `.venv` and run `python -m pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'llama_cpp'` | Install `llama-cpp-python` with the CPU wheel command above |
| `npm.ps1 cannot be loaded` | Use `npm.cmd` instead of `npm` |
| Frontend cannot call API | Make sure backend is running at `http://localhost:3003` |
| Gemini old models fail | Use only `gemini-2.5-flash`, `gemini-2.5-flash-lite`, or `gemini-3.1-flash-lite` |
| Local model not found | Put the `.gguf` file at the path in `LOCAL_MODEL_PATH` |
| ReAct is slower than Baseline | Expected: ReAct uses tool calls and multi-step reasoning |

---

## 10. Recommended Development Flow

Use three terminals:

```text
Terminal 1: python api_server.py
Terminal 2: cd frontend && npm.cmd run dev
Terminal 3: python -m pytest / npm.cmd test
```

Then open:

```text
http://localhost:5173
```

Ask Vietnamese product questions such as:

```text
Trả lời bằng tiếng Việt. Tôi cần một con chuột dưới 500000 VND, đánh giá ít nhất 4.6 sao và giao trong tối đa 3 ngày.
```

---

## 11. Important Files

| Path | Purpose |
|---|---|
| `api_server.py` | FastAPI backend |
| `src/chat/baseline.py` | Baseline chatbot |
| `src/agent/agent.py` | ReAct agent loop |
| `src/tools/catalog_tools.py` | Catalog search/compare/cart tools |
| `src/database/banggia.xlsx` | Product catalog |
| `src/core/*_provider.py` | OpenAI, Gemini, and local provider adapters |
| `frontend/src/components/AppShell.tsx` | Main React UI |
| `frontend/src/data/mockApi.ts` | Frontend API adapter and conversation persistence |
| `logs/YYYY-MM-DD.log` | Runtime telemetry logs |

