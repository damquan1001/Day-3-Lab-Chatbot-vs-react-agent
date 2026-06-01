"""
HTTP API for chatbot baseline (FE integration).
Default port: 3003 (API_PORT in .env).

Run:
  python api_server.py
  # or: uvicorn api_server:app --host 0.0.0.0 --port 3003
"""
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.agent.agent import ReActAgent
from src.chat.baseline import ChatbotBaseline, get_llm
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.tools.catalog_tools import build_catalog_tools

load_dotenv()

_llm: Optional[LLMProvider] = None
_sessions: dict[str, ChatbotBaseline] = {}
_tools: list[dict[str, Any]] = []
_api_events: list[dict[str, Any]] = []
_provider: str = ""


def _parse_cors_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3003,http://localhost:5173,http://127.0.0.1:5173",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _llm, _provider, _tools
    _provider = os.getenv("DEFAULT_PROVIDER", "openai")
    logger.log_event("API_START", {"provider": _provider, "port": os.getenv("API_PORT", "3003")})
    try:
        _llm = get_llm(_provider, quiet=True)
        _tools = build_catalog_tools()
    except (FileNotFoundError, ValueError) as e:
        logger.log_event("API_START_FAILED", {"error": str(e)})
        raise
    yield
    logger.log_event("API_SHUTDOWN", {"sessions": len(_sessions)})
    _sessions.clear()


app = FastAPI(
    title="Lab 3 Chatbot API",
    description="Baseline chatbot for frontend (no tools / no ReAct)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    model: str
    provider: Optional[str] = None
    usage: Optional[dict] = None
    latency_ms: Optional[int] = None


class CompareResponse(BaseModel):
    baseline: dict[str, Any]
    react: dict[str, Any]
    turn: dict[str, Any]
    session_id: str
    telemetry: list[dict[str, Any]]
    usage: dict[str, Any]


def _get_session(session_id: Optional[str]) -> tuple[str, ChatbotBaseline]:
    if _llm is None:
        raise HTTPException(status_code=503, detail="LLM not loaded")
    sid = session_id or str(uuid.uuid4())
    if sid not in _sessions:
        _sessions[sid] = ChatbotBaseline(_llm)
    return sid, _sessions[sid]


def _provider_name() -> str:
    return _provider or os.getenv("DEFAULT_PROVIDER", "openai")


def _usage_cost(total_tokens: int) -> float:
    return round((total_tokens / 1000) * 0.01, 4)


def _agent_response(
    kind: str,
    title: str,
    content: str,
    latency_ms: int,
    usage: Optional[dict[str, Any]] = None,
    steps: int = 1,
    status: str = "success",
    error_code: Optional[str] = None,
) -> dict[str, Any]:
    usage = usage or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "kind": kind,
        "title": title,
        "content": content,
        "latencyMs": latency_ms,
        "promptTokens": prompt_tokens,
        "completionTokens": completion_tokens,
        "totalTokens": total_tokens,
        "costEstimate": _usage_cost(total_tokens),
        "status": status,
        "errorCode": error_code,
        "steps": steps,
    }


def _record_event(
    event: str,
    response: dict[str, Any],
    step_count: int,
    error_code: Optional[str] = None,
) -> dict[str, Any]:
    telemetry_event = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
        "provider": _provider_name(),
        "model": _llm.model_name if _llm else "unknown",
        "latencyMs": response.get("latencyMs", 0),
        "promptTokens": response.get("promptTokens", 0),
        "completionTokens": response.get("completionTokens", 0),
        "totalTokens": response.get("totalTokens", 0),
        "costEstimate": response.get("costEstimate", 0),
        "stepCount": step_count,
        "errorCode": error_code,
    }
    _api_events.insert(0, telemetry_event)
    del _api_events[100:]
    return telemetry_event


def _usage_summary() -> dict[str, Any]:
    if not _api_events:
        return {"totalTokens": 0, "estimatedCost": 0, "averageLatencyMs": 0}

    total_tokens = sum(int(event.get("totalTokens", 0)) for event in _api_events)
    estimated_cost = round(sum(float(event.get("costEstimate", 0)) for event in _api_events), 4)
    average_latency = sum(int(event.get("latencyMs", 0)) for event in _api_events) / len(
        _api_events
    )
    return {
        "totalTokens": total_tokens,
        "estimatedCost": estimated_cost,
        "averageLatencyMs": round(average_latency),
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": _provider,
        "model": _llm.model_name if _llm else None,
        "sessions": len(_sessions),
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        sid, bot = _get_session(req.session_id)
        data = bot.complete(req.message.strip())
    except Exception as e:
        logger.log_event("API_CHAT_ERROR", {"error": str(e)})
        raise HTTPException(status_code=502, detail=str(e)) from e

    return ChatResponse(
        reply=data["reply"],
        session_id=sid,
        model=data["model"],
        provider=data.get("provider"),
        usage=data.get("usage"),
        latency_ms=data.get("latency_ms"),
    )


@app.post("/api/compare", response_model=CompareResponse)
def compare(req: ChatRequest):
    sid, bot = _get_session(req.session_id)
    prompt = req.message.strip()

    try:
        baseline_data = bot.complete(prompt)
        baseline = _agent_response(
            kind="baseline",
            title="Baseline Chatbot",
            content=baseline_data["reply"],
            latency_ms=int(baseline_data.get("latency_ms") or 0),
            usage=baseline_data.get("usage") or {},
            steps=1,
        )
    except Exception as e:
        logger.log_event("API_BASELINE_ERROR", {"error": str(e)})
        baseline = _agent_response(
            kind="baseline",
            title="Baseline Chatbot",
            content=f"Baseline failed: {e}",
            latency_ms=0,
            status="error",
            error_code="BASELINE_ERROR",
        )

    try:
        if _llm is None:
            raise RuntimeError("LLM not loaded")
        start = time.time()
        agent = ReActAgent(llm=_llm, tools=_tools, max_steps=5)
        answer = agent.run(prompt)
        latency_ms = int((time.time() - start) * 1000)
        metrics = dict(agent.last_run_metrics)
        metrics["latency_ms"] = metrics.get("latency_ms") or latency_ms
        react = _agent_response(
            kind="react",
            title="ReAct Agent",
            content=answer,
            latency_ms=latency_ms,
            usage=metrics,
            steps=int(metrics.get("steps", 0) or 1),
        )
    except Exception as e:
        logger.log_event("API_REACT_ERROR", {"error": str(e)})
        react = _agent_response(
            kind="react",
            title="ReAct Agent",
            content=f"ReAct agent failed: {e}",
            latency_ms=0,
            status="error",
            error_code="REACT_ERROR",
        )

    turn = {
        "id": str(uuid.uuid4()),
        "prompt": prompt,
        "createdAt": datetime.utcnow().isoformat(),
        "baseline": baseline,
        "react": react,
    }

    new_events = [
        _record_event("CHATBOT_BASELINE", baseline, baseline.get("steps", 1), baseline.get("errorCode")),
        _record_event("AGENT_END", react, react.get("steps", 1), react.get("errorCode")),
    ]

    return CompareResponse(
        baseline=baseline,
        react=react,
        turn=turn,
        session_id=sid,
        telemetry=new_events,
        usage=_usage_summary(),
    )


@app.get("/api/telemetry")
def telemetry():
    return _api_events


@app.get("/api/usage")
def usage():
    return _usage_summary()


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    try:
        sid, bot = _get_session(req.session_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    def event_generator():
        yield f"event: session\ndata: {json.dumps({'session_id': sid})}\n\n"
        try:
            for token in bot.stream_tokens(req.message.strip()):
                payload = json.dumps({"token": token})
                yield f"data: {payload}\n\n"
            yield "event: done\ndata: {}\n\n"
        except Exception as e:
            err = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {err}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.delete("/api/session/{session_id}")
def clear_session(session_id: str):
    removed = _sessions.pop(session_id, None) is not None
    return {"session_id": session_id, "removed": removed}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "3003"))
    uvicorn.run("api_server:app", host=host, port=port, reload=False)
