"""
HTTP API for chatbot baseline (FE integration).
Default port: 3003 (API_PORT in .env).

Run:
  python api_server.py
  # or: uvicorn api_server:app --host 0.0.0.0 --port 3003
"""
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.chat.baseline import ChatbotBaseline, get_llm
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger

load_dotenv()

_llm: Optional[LLMProvider] = None
_sessions: dict[str, ChatbotBaseline] = {}
_provider: str = ""


def _parse_cors_origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:3003,http://localhost:5173,http://127.0.0.1:5173",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _llm, _provider
    _provider = os.getenv("DEFAULT_PROVIDER", "openai")
    logger.log_event("API_START", {"provider": _provider, "port": os.getenv("API_PORT", "3003")})
    try:
        _llm = get_llm(_provider, quiet=True)
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


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    model: str
    provider: Optional[str] = None
    usage: Optional[dict] = None
    latency_ms: Optional[int] = None


def _get_session(session_id: Optional[str]) -> tuple[str, ChatbotBaseline]:
    if _llm is None:
        raise HTTPException(status_code=503, detail="LLM not loaded")
    sid = session_id or str(uuid.uuid4())
    if sid not in _sessions:
        _sessions[sid] = ChatbotBaseline(_llm)
    return sid, _sessions[sid]


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
