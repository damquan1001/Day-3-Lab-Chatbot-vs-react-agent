# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Lê Đàm Quân
- **Student ID**: 2A202600930
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

*Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.).*

- **Modules Implementated**: `api_server.py`, `frontend/src/components/AppShell.tsx`, `frontend/src/data/mockApi.ts`, `frontend/src/components/MarkdownContent.tsx`, `frontend/src/store/useAppStore.ts`, `frontend/src/types.ts`, `src/core/gemini_provider.py`, `src/chat/baseline.py`, `tests/test_api_server.py`, `frontend/src/App.test.tsx`
- **Code Highlights**:
  - Added `/api/compare/stream` in `api_server.py` so the Baseline response can be emitted first and the ReAct response can arrive later without blocking the UI.
  - Updated `frontend/src/data/mockApi.ts` to consume Server-Sent Events from `/api/compare/stream`, update each response panel independently, and fall back to `/api/compare` when streaming is unavailable.
  - Added `frontend/src/components/MarkdownContent.tsx` so LLM answers written in Markdown render as headings, lists, inline code, code fences, bold text, italic text, and links instead of plain text.
  - Added `localStorage` persistence for conversations and turns in `frontend/src/data/mockApi.ts`, with `conversationId` added to `ChatTurn` in `frontend/src/types.ts`.
  - Restricted Gemini model choices to `gemini-2.5-flash`, `gemini-2.5-flash-lite`, and `gemini-3.1-flash-lite` in both frontend options and backend provider validation.
  - Added tests for streaming event order, old Gemini model rejection, and updated frontend behavior.
- **Documentation**: These changes connect the ReAct loop to the production-style UI flow. The backend still executes Baseline and ReAct through the same provider, but streaming allows the UI to show Baseline immediately while ReAct continues its Thought-Action-Observation loop. Markdown rendering and conversation persistence make the comparison output easier to inspect across reloads.

---

## II. Debugging Case Study (10 Points)

*Analyze a specific failure event you encountered during the lab using the logging system.*

- **Problem Description**: The frontend originally waited for both Baseline and ReAct to finish before displaying anything. This made the app feel slow because the Baseline often completed in 3-6 seconds, while ReAct could take 19-25 seconds on multi-step prompts.
- **Log Source**: `logs/2026-06-01.log` showed ReAct latency-heavy traces and `AGENT_FINAL_TOO_THIN` cases. One related trace was:

```text
{"event": "AGENT_FINAL_TOO_THIN", "data": {"step": 1, "answer_preview": "Keychron K2 V2 là lựa chọn tốt."}}
```

- **Diagnosis**: The backend only had `/api/compare`, which returns one combined payload after both systems finish. The ReAct loop also intentionally performs multiple LLM/tool steps and sometimes rewrite steps, so the slowest model path controlled the whole user experience. This was a UI/API contract issue, not a frontend rendering issue alone.
- **Solution**: I added `/api/compare/stream` using Server-Sent Events. The endpoint emits `session`, then `baseline`, then `react`, then `done`. The frontend now updates `pendingTurn.baseline` as soon as the Baseline event arrives and separately updates `pendingTurn.react` when the ReAct event arrives. I also added `test_compare_stream_emits_baseline_before_react()` to make sure this behavior does not regress.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflect on the reasoning capability difference.*

1.  **Reasoning**: The `Thought` block gives the ReAct agent an explicit planning step before it chooses a tool. This makes the answer more grounded when the user asks for filtering, sorting, tradeoffs, or multi-condition comparisons. The direct chatbot can answer quickly, but it reasons over one large CSV prompt and cannot verify intermediate facts through tools.
2.  **Reliability**: The Agent performed worse when the task was simple or outside the catalog. For example, the "laptop" prompt was handled gracefully by the Baseline because it could scan the pasted catalog and state that no laptop category exists. ReAct failed because the Gemini provider raised an exception when `response.text` had no valid text part.
3.  **Observation**: Observations are the main advantage of ReAct. When `compare_products` returns structured product rows, the next Thought can compare price, rating, and delivery more accurately. However, if an Observation is empty, too large, or caused by a poorly chosen query, the agent may spend extra steps trying to recover.

---

## IV. Future Improvements (5 Points)

*How would you scale this for a production-level AI agent system?*

- **Scalability**: Move conversation persistence from browser `localStorage` to a server database keyed by user/session, so conversations survive across devices and browsers.
- **Safety**: Add deterministic pre-LLM guardrails for prompt injection, API key extraction, fraud, cyber abuse, and harmful physical instructions. These prompts should be refused before the ReAct loop spends tool and model budget.
- **Performance**: Add a fast path for simple lookup prompts. If the user only asks for the cheapest product in one category, the backend can call `compare_products` directly or allow a concise ReAct answer instead of forcing a long final recommendation.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
