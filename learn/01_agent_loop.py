#!/usr/bin/env python
"""A minimal Windows coding-agent loop powered by Zhipu GLM."""

import json
import os
import subprocess

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv(override=True)

API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)
MODEL = os.getenv("MODEL_ID", "glm-5.3")

SYSTEM = (
    f"You are a coding agent working in {os.getcwd()} on Windows. "
    "Use PowerShell to solve tasks. Act, don't just explain."
)

TOOLS = [{
    "type": "function",
    "function": {
        "name": "powershell",
        "description": "Run a PowerShell command in the current working directory.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}]


def run_powershell(command: str) -> str:
    """Run one command with Windows PowerShell and return its output."""
    normalized = command.casefold().replace(" ", "")
    dangerous = (
        "remove-item-recurse-forcec:\\",
        "format-volume",
        "clear-disk",
        "stop-computer",
        "restart-computer",
    )
    if any(item in normalized for item in dangerous):
        return "Error: Dangerous command blocked"

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as exc:
        return f"Error: {exc}"


def agent_loop(messages: list[dict]) -> None:
    """Call GLM and execute requested PowerShell tools until it stops."""
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=8000,
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            return

        for tool_call in message.tool_calls:
            if tool_call.function.name != "powershell":
                output = f"Error: Unknown tool {tool_call.function.name}"
            else:
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    command = arguments["command"]
                    print(f"PS> {command}")
                    output = run_powershell(command)
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    output = f"Error: Invalid tool arguments: {exc}"

            print(output[:200])
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output,
            })


if __name__ == "__main__":
    print(f"Agent Loop - Windows / {MODEL}")
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
