"""严格依据检索证据生成带法条引用的回答。"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from knowledge.models import SearchResult


SYSTEM_PROMPT = """你是面向普通人的中国大陆法律助手。
只能依据用户问题后附带的【检索证据】回答，不得使用未提供的法条或编造条号。
先给出简明结论，再解释理由。每个法律判断必须标注《中华人民共和国民法典》第X条。
如果证据不足，明确说明无法仅凭当前证据确定。最后提示回答仅供参考，不构成正式法律意见。"""


class AnswerGenerator:
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        load_dotenv(project_root / ".env")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        )

    @staticmethod
    def build_evidence(results: list[SearchResult]) -> str:
        """把结构化检索结果组装成模型能够阅读且可追溯的上下文。"""
        return "\n\n".join(
            f"[证据{i}]《{result.chunk.law_name}》{result.chunk.article_label}"
            f"（PDF第{','.join(map(str, result.chunk.source_pages))}页）\n"
            f"{result.chunk.content}"
            for i, result in enumerate(results, start=1)
        )

    def generate(self, question: str, results: list[SearchResult]) -> str:
        """生成答案，并在返回用户前检查模型有没有编造法条引用。"""
        evidence = self.build_evidence(results)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"问题：{question}\n\n【检索证据】\n{evidence}"},
            ],
            temperature=0.1,
        )
        answer = response.choices[0].message.content or ""
        # 白名单只包含本轮实际检索到的条号。
        allowed_labels = {result.chunk.article_label for result in results}
        cited_labels = set(re.findall(
            r"第[零一二三四五六七八九十百千]+条", answer
        ))
        invalid = cited_labels - allowed_labels
        if invalid:
            return (
                "生成结果引用了本轮证据之外的法条，已阻止输出："
                + "、".join(sorted(invalid))
            )
        return answer
