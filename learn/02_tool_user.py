#!/usr/bin/env python
"""在 01_agent_loop.py 的基础上增加文件工具和统一工具分发。"""

import glob as glob_module
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

WORKDIR = Path.cwd().resolve()
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)
MODEL = os.getenv("MODEL_ID", "glm-5.3")
SYSTEM = (
    f"You are a coding agent working in {WORKDIR} on Windows. "
    "Use the provided tools to solve tasks. Act, don't just explain."
)


# -- 继承自 01：PowerShell 工具 --

def run_powershell(command: str) -> str:
    """Run one command with Windows PowerShell and return its output."""
    normalized = command.casefold().replace(" ", "")
    dangerous = (
        "remove-item-recurse-forcec:\\", "format-volume", "clear-disk",
        "stop-computer", "restart-computer",
    )
    if any(item in normalized for item in dangerous):
        return "Error: Dangerous command blocked"
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=WORKDIR, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as exc:
        return f"Error: {exc}"


# -- 02 新增：文件工具 --

def safe_path(path: str) -> Path:
    """Resolve a path and ensure it remains inside the workspace."""
    resolved = (WORKDIR / path).resolve()
    if not resolved.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {path}")
    return resolved


def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        if limit is not None and limit >= 0 and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as exc:
        return f"Error: {exc}"


def run_write(path: str, content: str) -> str:
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content.encode('utf-8'))} bytes to {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        file_path = safe_path(path)
        text = file_path.read_text(encoding="utf-8")
        if old_text not in text:
            return f"Error: text not found in {path}"
        file_path.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_glob(pattern: str) -> str:
    try:
        matches = sorted({
            match for match in glob_module.glob(
                pattern, root_dir=WORKDIR, recursive=True
            ) if safe_path(match).is_relative_to(WORKDIR)
        })
        shown = matches[:200]
        if len(matches) > 200:
            shown.append("... (more matches omitted; narrow the pattern)")
        return "\n".join(shown) if shown else "(no matches)"
    except Exception as exc:
        return f"Error: {exc}"


def function_tool(name: str, description: str, properties: dict,
                  required: list[str]) -> dict:
    """Build one OpenAI-compatible function-tool definition."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object", "properties": properties,
                "required": required,
            },
        },
    }


# 由 01 的一个工具扩展为五个；schema 全部使用 OpenAI 格式。
TOOLS = [
    function_tool(
        "powershell", "Run a PowerShell command in the current working directory.",
        {"command": {"type": "string"}}, ["command"],
    ),
    function_tool(
        "read_file", "Read a UTF-8 text file inside the workspace.",
        {"path": {"type": "string"},
         "limit": {"type": "integer", "minimum": 0}}, ["path"],
    ),
    function_tool(
        "write_file", "Write UTF-8 content to a file inside the workspace.",
        {"path": {"type": "string"}, "content": {"type": "string"}},
        ["path", "content"],
    ),
    function_tool(
        "edit_file", "Replace the first exact text match in a workspace file.",
        {"path": {"type": "string"}, "old_text": {"type": "string"},
         "new_text": {"type": "string"}},
        ["path", "old_text", "new_text"],
    ),
    function_tool(
        "glob", "Find workspace files matching a glob pattern; ** is recursive.",
        {"pattern": {"type": "string"}}, ["pattern"],
    ),
]


# 02 的核心增量：按工具名分发，不再在循环里写死 powershell。
TOOL_HANDLERS: dict[str, Callable[..., str]] = {
    "powershell": run_powershell,
    "read_file": run_read,
    "write_file": run_write,
    "edit_file": run_edit,
    "glob": run_glob,
}


def dispatch_tool(name: str, arguments_json: str) -> str:
    """Decode and dispatch one OpenAI-compatible function call."""
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return f"Error: Unknown tool {name}"
    try:
        arguments: dict[str, Any] = json.loads(arguments_json)
        if not isinstance(arguments, dict):
            raise TypeError("tool arguments must be a JSON object")
        return handler(**arguments)
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        return f"Error: Invalid tool arguments: {exc}"


def agent_loop(messages: list[dict]) -> None:
    """Call the model and dispatch requested tools until it stops."""
    while True:
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS,
            tool_choice="auto", max_tokens=8000,
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            return

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            print(f"> {name}")
            output = dispatch_tool(name, tool_call.function.arguments)
            print(output[:200])
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output,
            })


if __name__ == "__main__":
    print(f"Tool Use - Windows / {MODEL}")
    print("输入问题后按 Enter 发送；输入 q 退出。\n")
    history: list[dict] = [{"role": "system", "content": SYSTEM}]
    while True:
        try:
            query = input("agent >> ")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        history.append({"role": "user", "content": query})
        try:
            agent_loop(history)
            content = history[-1].get("content")
            if content:
                print(content)
        except Exception as exc:
            print(f"调用失败: {exc}")
