# app/main.py
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel

from openai import OpenAI

try:
    from google.cloud import firestore  # 在 Cloud Run 上可用，本地没装也不会影响运行
except Exception:  # pragma: no cover
    firestore = None

# ========== OpenAI 客户端 ==========

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client: Optional[OpenAI] = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# ========== Firestore 客户端（惰性初始化） ==========

_firestore_client = None


def get_firestore_client():
    global _firestore_client
    if _firestore_client is None and firestore is not None:
        try:
            # 在 Cloud Run 上会自动使用当前项目的服务账号
            _firestore_client = firestore.Client()
        except Exception:
            _firestore_client = None
    return _firestore_client


# ========== FastAPI 应用 ==========

app = FastAPI(title="Her Cloud Core", version="1.3")


class ChatRequest(BaseModel):
    user_id: str
    input: str
    mode: str = "text"
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    emotion: str = "warm"
    conversation_id: str
    tokens_used: Dict[str, int]
    meta: Dict[str, Any] = {}


@app.get("/health")
async def health():
    """Cloud Run 健康检查用"""
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    主聊天接口：Her 控制台前端正在用的就是这个 /api/chat
    """
    # 如果没有配置 OpenAI KEY，至少服务能跑起来，给个提示
    if client is None:
        reply_text = "后端缺少 OPENAI_API_KEY，暂时不能调用大模型，不过服务已经正常启动啦。"
        return ChatResponse(
            reply=reply_text,
            emotion="warm",
            conversation_id=req.conversation_id or req.user_id,
            tokens_used={"input": 0, "output": 0},
            meta={"model": None, "source": "fallback", "mode": req.mode},
        )

    # 构造提示词（简单一点就好，重点是先跑通）
    system_prompt = (
        "你是 Her，一个温柔、懂车、懂机械的 AI 伙伴，说话自然、简短、口语化，"
        "偏中英混合但以中文为主。"
    )
    user_prompt = req.input

    completion = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        metadata={"user_id": req.user_id, "mode": req.mode},
    )

    # 新版 SDK 的取文本方式
    reply_text = completion.output[0].content[0].text

    tokens_in = getattr(getattr(completion, "usage", None), "input_tokens", 0) or 0
    tokens_out = getattr(getattr(completion, "usage", None), "output_tokens", 0) or 0

    conversation_id = req.conversation_id or req.user_id

    # ===== 把对话写入 Firestore（如果可用的话，不可用就忽略） =====
    db = get_firestore_client()
    if db is not None:
        try:
            doc_ref = db.collection("her_conversations").document(conversation_id)
            doc_ref.collection("messages").add(
                {
                    "user_id": req.user_id,
                    "input": req.input,
                    "reply": reply_text,
                    "mode": req.mode,
                    "created_at": datetime.now(timezone.utc),
                    "tokens_input": tokens_in,
                    "tokens_output": tokens_out,
                    "firestore_db_id": db._database if hasattr(db, "_database") else None,
                }
            )
        except Exception:
            # 出错也不要影响主流程
            pass

    return ChatResponse(
        reply=reply_text,
        emotion="warm",
        conversation_id=conversation_id,
        tokens_used={"input": tokens_in, "output": tokens_out},
        meta={"model": getattr(completion, "model", None), "mode": req.mode},
    )
