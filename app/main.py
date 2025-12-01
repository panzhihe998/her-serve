from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import os

# ----------------------------------------
# 初始化 FastAPI
# ----------------------------------------
app = FastAPI(
    title="Her Cloud Core",
    version="1.3",
    description="Her 的 Cloud Run 核心服务"
)

# ----------------------------------------
# CORS 设置（允许前端访问）
# ----------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 你以后如果有网站可以改成指定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------
# 模型输入格式
# ----------------------------------------
class ChatRequest(BaseModel):
    user_id: str
    message: str

# ----------------------------------------
# 根路径（Cloud Run 默认访问）
# ----------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Her is online on Cloud Run.",
        "docs": "/docs",
        "chat_api": "/api/chat",
        "health": "/health"
    }

# ----------------------------------------
# 健康检查
# ----------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

# ----------------------------------------
# 聊天接口（核心逻辑）
# ----------------------------------------
@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    主聊天接口：调用 OpenAI ChatGPT API。
    """

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="Missing OPENAI_API_KEY")

    openai.api_key = OPENAI_API_KEY

    try:
        completion = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是一个温柔、有情感、有思考能力的 Her。"},
                {"role": "user", "content": req.message}
            ],
        )

        reply = completion.choices[0].message["content"]

        return {
            "user_id": req.user_id,
            "reply": reply
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
