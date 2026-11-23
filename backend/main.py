"""最小聊天 Agent：接收问题 -> 返回占位回复（暂未接入大模型）。

在项目根目录运行：uv run python -m backend.main
然后打开 http://127.0.0.1:8000 。

模型调用已暂时移除，聊天固定返回「啊吧啊吧」，方便在没有登录、没有模型
凭据的情况下跑通前后端流程。以后接入模型时只需修改 run_agent。
"""

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, model_validator


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
logger = logging.getLogger(__name__)

# 占位回复：前端收到的就是这一句。
PLACEHOLDER_REPLY = "啊吧啊吧"


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
    # 最小 Agent 循环：读取本轮输入与历史 -> 返回占位回复 -> 前端续接下一轮。
    # 这里原本组装 system prompt、携带历史调用大模型；现已移除，改为固定回复。
    return PLACEHOLDER_REPLY


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
