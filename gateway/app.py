"""法律助手 — 最小可跑闭环：无 RAG 的聊天机器人后端。

只做一件事：接收前端消息 → 调 DeepSeek 流式生成 → SSE 推回前端。
后续在此基础上逐步加 RAG、分层记忆、MCP 工具。
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

# 加载 .env（若存在）；不存在则回退到系统环境变量
load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

if not DEEPSEEK_API_KEY:
    raise RuntimeError(
        "未找到 DEEPSEEK_API_KEY：请复制 .env 为 .env 并填写，或设置系统环境变量"
    )

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

app = FastAPI(title="法律助手（测试版）")

SYSTEM_PROMPT = (
    "你是一个中文法律助手。请用通俗易懂的大白话回答用户的法律问题，"
    "先给出明确结论，再简要说明理由。"
    "如果问题涉及个案具体情况或超出你的知识范围，请提示用户咨询专业律师。"
    "注意：你的回答仅供参考，不构成正式法律意见。"
)


@app.post("/api/chat")
async def chat(req: Request):
    data = await req.json()
    messages = data.get("messages", [])
    # 在消息列表最前面插入 system prompt
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    stream = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=full_messages,
        stream=True,
    )

    async def event_stream():
        try:
            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield f"data: {json.dumps({'content': delta}, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# 托管前端静态文件（放在最后，避免拦截 /api 路由）
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
