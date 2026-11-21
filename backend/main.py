"""最小聊天 Agent：接收问题 -> 携带对话历史调用模型 -> 返回回复。

在项目根目录运行：uv run python -m backend.main
然后打开 http://127.0.0.1:8000 。配置读取根目录 .env：
LLM_API_KEY、LLM_BASE_URL，以及可选的 LLM_MODEL（默认使用 config.py）。
"""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    AuthenticationError,
    RateLimitError,
)
from pydantic import BaseModel, Field, ValidationError, model_validator

from config import DEFAULT_CONFIG


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
logger = logging.getLogger(__name__)
SYSTEM_PROMPT = (
    "你是法律助手小王，用清晰、友好的中文与用户交流。"
    "结合对话上下文回答；信息不足时主动询问。"
    "涉及法律问题时区分事实、推测和建议，不编造法条、案例或来源。"
    "当前没有联网检索或知识库工具，不要声称已查询资料。"
)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=10000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def validate_conversation(self):
        for index, message in enumerate(self.messages):
            expected_role = "user" if index % 2 == 0 else "assistant"
            if message.role != expected_role or not message.content.strip():
                raise ValueError("消息必须非空，并按 user、assistant 顺序交替")
        if self.messages[-1].role != "user":
            raise ValueError("最后一条消息必须是用户问题")
        return self


class ChatError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def run_agent(request: ChatRequest) -> str:
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        raise ChatError(503, "请先在项目根目录 .env 中配置 LLM_API_KEY，然后重启服务。")

    # 最小 Agent 循环：读取本轮输入与历史 -> 调用模型 -> 将回复交给前端续接下一轮。
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(message.model_dump() for message in request.messages)
    try:
        with OpenAI(
            api_key=api_key,
            base_url=os.getenv("LLM_BASE_URL", "").strip() or "https://api.deepseek.com/v1",
            timeout=60.0,
            max_retries=0,
        ) as client:
            result = client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "").strip() or DEFAULT_CONFIG.llm_model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )
    except AuthenticationError:
        raise ChatError(502, "模型认证失败，请检查后端 LLM_API_KEY 配置。") from None
    except RateLimitError:
        raise ChatError(429, "模型请求受限或余额不足，请稍后重试并检查模型账户。") from None
    except APITimeoutError:
        raise ChatError(504, "模型响应超时，请稍后重试。") from None
    except APIConnectionError:
        raise ChatError(502, "无法连接模型服务，请检查后端网络和 LLM_BASE_URL。") from None
    except APIStatusError as exc:
        logger.warning("Model API returned HTTP %s", exc.status_code)
        raise ChatError(502, "模型调用失败，请检查 LLM_MODEL、接口地址及模型账户权限。") from None

    reply = result.choices[0].message.content if result.choices else None
    if not reply or not reply.strip():
        raise ChatError(502, "模型返回了空回复，请重试。")
    return reply


class ChatHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(90)

    def respond(self, status: int, data, content_type="application/json; charset=utf-8"):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # 页面与接口同源，一个服务即可运行前后端。
        if self.path != "/":
            self.respond(404, {"detail": "页面不存在"})
            return
        self.respond(200, (ROOT / "frontend" / "index.html").read_bytes(), "text/html; charset=utf-8")

    def do_POST(self):
        if self.path != "/api/chat":
            self.respond(404, {"detail": "接口不存在"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2_000_000:
                raise ChatError(413, "请求为空或过大，请缩短对话后重试。")
            request = ChatRequest.model_validate_json(self.rfile.read(length))
        except (ValueError, ValidationError):
            self.respond(422, {"detail": "消息格式无效：请交替发送用户与助手消息，最后一条必须是非空用户问题。"})
            return
        except ChatError as exc:
            self.respond(exc.status, {"detail": exc.detail})
            return

        try:
            reply = run_agent(request)
        except ChatError as exc:
            self.respond(exc.status, {"detail": exc.detail})
        except Exception:
            logger.exception("Chat request failed")
            self.respond(500, {"detail": "服务内部错误，请查看后端控制台后重试。"})
        else:
            self.respond(200, {"reply": reply})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    with ThreadingHTTPServer((host, port), ChatHandler) as server:
        print(f"法律助手小王已启动：http://{host}:{port} （Ctrl+C 停止）", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
