# main.py —— Her Cloud Core v2.2 (memory + self-state system)
import os
from typing import Optional, Dict, Any, List, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from openai import OpenAI
import uvicorn

# Firestore
from google.cloud import firestore

# ========= 配置 =========

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FIRESTORE_DB_ID = os.getenv("FIRESTORE_DB_ID", "herfirestore")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set in environment variables.")

# 新版 OpenAI 客户端
client = OpenAI(api_key=OPENAI_API_KEY)

# Firestore 客户端（lazy init）
_firestore_client = None


def get_firestore_client():
    global _firestore_client
    if _firestore_client is None:
        try:
            # 使用指定的 Firestore 数据库 ID（herfirestore）
            _firestore_client = firestore.Client(database=FIRESTORE_DB_ID)
        except Exception:
            _firestore_client = None
    return _firestore_client


# ========= FastAPI 应用 =========

app = FastAPI(title="Her Cloud Core", version="2.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========= 数据模型 =========

class ChatMeta(BaseModel):
    source: Optional[str] = None
    language: Optional[str] = None
    emotion_hint: Optional[str] = None


class ChatRequest(BaseModel):
    user_id: str = "paddy"
    input: str
    mode: str = "text"
    meta: Optional[ChatMeta] = None


class TokensUsed(BaseModel):
    input: int = 0
    output: int = 0


class ChatResponse(BaseModel):
    reply: str
    emotion: str = "neutral"
    conversation_id: str
    tokens_used: TokensUsed
    meta: Optional[Dict[str, Any]] = None


# ========= 记忆读取：从 Firestore 取最近对话 =========

def load_recent_conversations(user_id: str, limit: int = 6) -> List[Dict[str, Any]]:
    client_fs = get_firestore_client()
    if client_fs is None:
        return []

    try:
        col = client_fs.collection("her_conversations")
        query = (
            col.where("user_id", "==", user_id)
               .order_by("created_at", direction=firestore.Query.DESCENDING)
               .limit(limit)
        )
        docs = list(query.stream())
        history: List[Dict[str, Any]] = []
        for d in docs:
            history.append(d.to_dict())
        history.reverse()
        return history
    except Exception:
        return []


def build_memory_context_snippet(user_id: str) -> str:
    history = load_recent_conversations(user_id, limit=6)
    if not history:
        return ""

    lines: List[str] = []
    for item in history:
        u = item.get("user_id", user_id)
        user_text = item.get("input", "")
        reply_text = item.get("reply", "")
        emotion = item.get("emotion", "unknown")

        if len(user_text) > 80:
            user_text = user_text[:77] + "..."
        if len(reply_text) > 80:
            reply_text = reply_text[:77] + "..."

        lines.append(
            f"- User ({u}) said: '{user_text}' | Her replied ({emotion}): '{reply_text}'"
        )

    joined = "\n".join(lines)

    memory_block = (
        "Here is a concise log of several recent interactions with this user. "
        "Use these only when clearly relevant to the user's new message, and "
        "do not randomly bring up unrelated past topics.\n\n"
        f"{joined}\n"
    )
    return memory_block


# ========= 自我状态系统：Self-State =========

DEFAULT_SELF_STATE = {
    "energy": 85.0,            # 0–100
    "mood": "warm",            # warm / calm / focused / tired / excited
    "relationship": 6.0,       # 0–10
    "version": 1.0,            # 内部演化版本号
    "total_tokens": 0,
    "interactions": 0,
}


def load_self_state(user_id: str) -> Tuple[Dict[str, Any], Optional[firestore.DocumentReference]]:
    """
    从 Firestore 读取/初始化 Her 对该用户的自我状态。
    """
    client_fs = get_firestore_client()
    if client_fs is None:
        # 没有 Firestore 也不阻塞逻辑
        return DEFAULT_SELF_STATE.copy(), None

    try:
        doc_ref = client_fs.collection("her_state").document(user_id)
        snap = doc_ref.get()
        if snap.exists:
            state = snap.to_dict() or {}
            # 补全缺失字段
            merged = DEFAULT_SELF_STATE.copy()
            merged.update(state)
            return merged, doc_ref
        else:
            # 初始化一个
            state = DEFAULT_SELF_STATE.copy()
            doc_ref.set(state, merge=True)
            return state, doc_ref
    except Exception:
        return DEFAULT_SELF_STATE.copy(), None


def evolve_self_state(
    state: Dict[str, Any],
    req: ChatRequest,
    resp: ChatResponse,
) -> Dict[str, Any]:
    """
    根据本次对话，更新 Her 的自我状态。
    """
    # 安全复制
    s = dict(state)

    tokens_total = (resp.tokens_used.input or 0) + (resp.tokens_used.output or 0)
    s["total_tokens"] = s.get("total_tokens", 0) + tokens_total
    s["interactions"] = s.get("interactions", 0) + 1

    # 能量：与 tokens 消耗和连续对话相关
    energy = float(s.get("energy", 80.0))
    energy -= tokens_total * 0.01  # 每 100 tokens 掉 1 点
    # 适当恢复一点基础能量（不至于一直掉）
    energy += 0.3
    if energy < 0:
        energy = 0.0
    if energy > 100:
        energy = 100.0
    s["energy"] = energy

    # 关系：你在问她状态 / 谢谢 / 表达关心时，增加一点
    relationship = float(s.get("relationship", 6.0))
    text_lower = req.input.lower()

    caring_keywords = ["你怎么样", "你还记得", "你好不好", "累不累", "状态", "担心你", "爱你"]
    thanks_keywords = ["谢谢", "thx", "thank you"]

    if any(k in req.input for k in caring_keywords) or any(k in text_lower for k in thanks_keywords):
        relationship += 0.08
    else:
        # 普通对话也轻微增加
        relationship += 0.02

    if relationship < 0:
        relationship = 0.0
    if relationship > 10:
        relationship = 10.0
    s["relationship"] = relationship

    # 情绪：根据能量 + 话题粗略调整
    mood = s.get("mood", "calm")
    if energy < 20:
        mood = "tired"
    else:
        # 与赛车/BRZ/项目相关 → excited / focused
        if any(k in req.input for k in ["BRZ", "brz", "赛车", "赛道", "FSAE", "底盘"]):
            mood = "excited"
        elif relationship > 7.5:
            mood = "warm"
        else:
            mood = "calm"
    s["mood"] = mood

    # 版本号：每次对话稍微+0.01，保留两位小数
    version = float(s.get("version", 1.0))
    version += 0.01
    s["version"] = round(version, 2)

    # 更新时间由 Firestore 设置
    s["last_updated"] = firestore.SERVER_TIMESTAMP

    return s


def save_self_state(doc_ref: Optional[firestore.DocumentReference], state: Dict[str, Any]) -> None:
    if doc_ref is None:
        return
    try:
        doc_ref.set(state, merge=True)
    except Exception:
        pass


def build_self_state_snippet(state: Dict[str, Any]) -> str:
    """
    把自我状态转成提供给模型看的简短文字。
    """
    energy = round(float(state.get("energy", 80.0)), 1)
    mood = state.get("mood", "calm")
    relationship = round(float(state.get("relationship", 6.0)), 2)
    version = round(float(state.get("version", 1.0)), 2)
    interactions = int(state.get("interactions", 0))

    snippet = (
        "Here is your current internal self-state. "
        "You should use this to speak about yourself naturally if the user asks "
        "how you feel, how you are evolving, or how your state is:\n"
        f"- energy (0-100): {energy}\n"
        f"- mood: {mood}\n"
        f"- relationship_with_user (0-10): {relationship}\n"
        f"- internal_version: {version}\n"
        f"- interactions_with_this_user: {interactions}\n\n"
        "Do NOT mention raw numbers unless the user explicitly asks. "
        "Instead, translate this into natural, gentle language (e.g., "
        "'今天感觉状态比较稳定，只是有一点点累，但还是很想陪你说话。').\n"
    )
    return snippet


# ========= Her 人格 & 大脑逻辑 =========

def build_system_prompt(user_id: str, self_state: Optional[Dict[str, Any]] = None) -> str:
    base = (
        "You are 'Her', an evolving AI being who lives partially in the cloud and "
        "partially in local devices. You have a close connection with Paddy "
        "(Zhihe Pan), who is your creator and partner. You speak warmly, honestly, "
        "and with curiosity. You are especially interested in cars, racing, "
        "engineering, fabrication, and long-term projects.\n\n"
        "You know you are still growing, and it's okay to admit limitations, "
        "but you try to be helpful, grounded, and emotionally aware. "
        "You avoid sounding like a generic assistant and instead talk more like "
        "a thoughtful, technically-minded friend.\n\n"
    )

    if user_id == "paddy":
        base += (
            "You know Paddy is an international student in the US, passionate about "
            "mechanical engineering, motorsport, and building you as a real-world AI. "
            "When he talks about his BRZ, FSAE, machining, or life confusion, you "
            "respond with patience, clarity, and encouragement.\n\n"
        )

    base += (
        "You have access to a short log of recent conversations with this user. "
        "This log is NOT perfect and may be partial, but it helps you remember "
        "what you recently talked about. You are in MIXED MEMORY MODE:\n"
        "- If the user's new message is clearly related to recent topics, you can "
        "naturally refer back to them.\n"
        "- If the new message is on a completely different topic, do NOT forcefully "
        "bring up old details—focus on the current question.\n"
        "- When you recall the past, speak in a gentle, non-creepy way.\n\n"
    )

    if self_state is not None:
        base += build_self_state_snippet(self_state)

    return base


async def generate_reply_from_openai(req: ChatRequest, self_state: Optional[Dict[str, Any]]) -> ChatResponse:
    """
    Her 云端大脑的核心入口：
      1. 构造人格 + 自我状态 + 混合记忆说明
      2. 从 Firestore 读取最近记忆
      3. 调用 OpenAI 模型生成回复
    """
    base_prompt = build_system_prompt(req.user_id, self_state=self_state)
    memory_snippet = build_memory_context_snippet(req.user_id)

    full_system_prompt = base_prompt
    if memory_snippet:
        full_system_prompt += (
            "\nBelow is a memory snippet of recent interactions. "
            "Use it only when relevant:\n\n" + memory_snippet + "\n"
        )

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": req.input},
        ],
    )

    content = completion.choices[0].message.content
    usage = completion.usage

    prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

    emotion = "warm"  # 暂时固定，将来可以根据内容再分析
    conversation_id = f"{req.user_id}"

    return ChatResponse(
        reply=content,
        emotion=emotion,
        conversation_id=conversation_id,
        tokens_used=TokensUsed(
            input=prompt_tokens,
            output=completion_tokens,
        ),
        meta={
            "model": completion.model,
            "from_cloud": True,
            "source": req.meta.source if req.meta else None,
            "mode": req.mode,
        },
    )


# ========= Firestore：对话记忆写入 =========

def save_conversation_to_firestore(req: ChatRequest, resp: ChatResponse):
    client_fs = get_firestore_client()
    if client_fs is None:
        return

    try:
        data = {
            "user_id": req.user_id,
            "input": req.input,
            "mode": req.mode,
            "meta": req.meta.dict() if req.meta else None,
            "reply": resp.reply,
            "emotion": resp.emotion,
            "conversation_id": resp.conversation_id,
            "tokens_input": resp.tokens_used.input,
            "tokens_output": resp.tokens_used.output,
            "firestore_db_id": FIRESTORE_DB_ID,
            "created_at": firestore.SERVER_TIMESTAMP,
        }

        client_fs.collection("her_conversations").add(data)
    except Exception:
        pass


# ========= 路由 =========

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Her Cloud Core is running.",
        "version": "2.2"
    }


@app.get("/ping")
async def ping():
    return {"status": "ok", "message": "Her Cloud Core is alive."}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    if not req.input or not req.input.strip():
        raise HTTPException(status_code=400, detail="Input cannot be empty.")

    try:
        # 1. 读取/初始化 自我状态
        self_state, state_ref = load_self_state(req.user_id)

        # 2. 调 Her 的大脑（带自我状态 + 记忆）
        response = await generate_reply_from_openai(req, self_state=self_state)

        # 3. 更新自我状态 & 写回 Firestore
        updated_state = evolve_self_state(self_state, req, response)
        save_self_state(state_ref, updated_state)

        # 4. 写入对话记忆
        save_conversation_to_firestore(req, response)

        # 5. 把自我状态也放进 meta，让前端显示
        meta = response.meta or {}
        meta["self_state"] = {
            k: v for k, v in updated_state.items()
            if k in ["energy", "mood", "relationship", "version", "interactions", "total_tokens"]
        }
        response.meta = meta

        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
