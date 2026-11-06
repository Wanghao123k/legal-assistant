"""
生成集成模块
"""
import logging
import os
from typing import List

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from learn.rag.C8.rag_modules.prompt import QUERY_ROUTR_PROMPT, QUERY_REWRITE_PROMPT, QUERY_BASIC_PROMPT, \
    QUERY_STEP_PROMPT

load_dotenv()

logger = logging.getLogger(__name__)


class GenerationIntegrationModule:
    """生成继承模块 - 负责LLM继承和回答生成"""

    def __init__(self, model_name: str = "deepseek-v4-pro", temperature: float = 1.0, max_tokens: int = 2048):
        """
        初始化生成集成模块

        Args:
            model_name: 模型名称
            temperature: 生成温度
            max_tokens: 最大token数
        """
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.llm = None
        self.setup_llm()

    def setup_llm(self):
        """初始化大语言模型"""
        logger.info(f"正在初始化LLM: {self.model_name}")
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_BASE_URL")
        if not api_key:
            raise ValueError("请设置 LLM_API_KEY 环境变量")
        if not base_url:
            raise ValueError("请设置 LLM_BASE_URL 环境变量")

        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            api_key=api_key,
            base_url=base_url
        )

        logger.info("LLM初始化完成")

    @classmethod
    def _build_context(cls, docs: List[Document], max_length: int = 2000) -> str:
        """
        构建上下文字符串

        Args:
            docs: 文档列表
            max_length: 最大长度

        Returns:
            格式化的上下文字符串
        """
        if not docs:
            return "暂无相关食谱信息"
        context_parts = []
        current_length = 0

        for i, doc in enumerate(docs, 1):
            # 添加元数据信息
            metadata_info = f"【食谱{i}】"
            if 'dish_name' in doc.metadata:
                metadata_info += f" {doc.metadata['dish_name']}"
            if 'category' in doc.metadata:
                metadata_info += f" | 分类: {doc.metadata['category']}"
            if 'difficulty' in doc.metadata:
                metadata_info += f" | 难度: {doc.metadata['difficulty']}"

            # 构建文档文本
            doc_text = f"{metadata_info}\n{doc.page_content}\n"

            # 检查长度限制
            if current_length + len(doc_text) > max_length:
                break

            context_parts.append(doc_text)
            current_length += len(doc_text)

        divider = "\n" + "=" * 50 + "\n"
        return divider + divider.join(context_parts)

    def query_router(self, query: str) -> str:
        """查询路由 - 根据查询类型选择不同的处理方式"""
        prompt = ChatPromptTemplate.from_template(QUERY_ROUTR_PROMPT)
        # RunnablePassthrough 是 LangChain 的“原样传递”组件：输入什么，就输出什么。
        chain = (
            {"query": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )

        result = chain.invoke(query).strip().lower()

        # 确保返回有效的路由类型
        if result in ['list', 'detail', 'general']:
            return result
        else:
            return 'general'  # 默认类型


    def query_rewrite(self, query: str) -> str:
        """
        智能查询重写 - 让大模型判断是否需要重写查询

        Args:
            query: 原始查询

        Returns:
            重写后的查询或原查询
        """
        prompt = PromptTemplate(template=QUERY_REWRITE_PROMPT, input_variables=["query"])
        chain = (
            {"query": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )

        response = chain.invoke(query).strip()

        # 记录重写结果
        # 记录重写结果
        if response != query:
            logger.info(f"查询已重写: '{query}' → '{response}'")
        else:
            logger.info(f"查询无需重写: '{query}'")

        return response


    def generate_list_answer(self, query: str, context_docs: List[Document]) -> str:
        """
        生成列表式回答 - 适用于推荐类查询
        """

        if not context_docs:
            return "抱歉， 没有找到相关的菜品信息"

        # 提取菜品名称
        dish_names = []
        for doc in context_docs:
            dish_name = doc.metadata.get('dish_name', "未知菜品")
            if dish_name not in dish_names:
                dish_names.append(dish_name)

        # 构建简洁的列表回答
        if len(dish_names) == 1:
            return f"为您推荐：{dish_names[0]}"
        elif len(dish_names) <= 3:
            return f"为您推荐以下菜品：\n" + "\n".join([f"{i+1}. {name}" for i, name in enumerate(dish_names)])
        else:
            return (
                    f"为您推荐以下菜品：\n" + "\n".join([f"{i+1}. {name}" for i, name in enumerate(dish_names[:3])]) +
                    f"\n\n还有其他 {len(dish_names)-3} 道菜品可供选择。"
            )

    def generate_basic_answer(self, query: str, context_docs: List[Document]) -> str:
        context = self._build_context(context_docs)

        prompt = ChatPromptTemplate.from_template(QUERY_BASIC_PROMPT)

        chain = (
            {"question": RunnablePassthrough(), "context": lambda _: context}
            | prompt
            | self.llm
            | StrOutputParser()
        )

        response = chain.invoke(query)
        return response

    def generate_basic_answer_stream(self, query: str, context_docs: List[Document]):
        """
        生成基础回答 - 流式输出

        Args:
            query: 用户查询
            context_docs: 上下文文档列表

        Yields:
            生成的回答片段
        """
        context = self._build_context(context_docs)

        prompt = ChatPromptTemplate.from_template(QUERY_BASIC_PROMPT)

        chain = (
            {"question": RunnablePassthrough(), "context": lambda _: context}
            | prompt
            | self.llm
            | StrOutputParser()
        )

        for chunk in chain.stream(query):
            yield chunk

    def generate_step_by_step_answer(self, query: str, context_docs: List[Document]) -> str:
        context = self._build_context(context_docs)

        prompt = ChatPromptTemplate.from_template(QUERY_STEP_PROMPT)
        chain = (
            {"question": RunnablePassthrough(), "context": lambda _: context}
            | prompt
            | self.llm
            | StrOutputParser()
        )

        return chain.invoke(query)


    def generate_step_by_step_answer_stream(self, query: str, context_docs: List[Document]):
        context = self._build_context(context_docs)

        prompt = ChatPromptTemplate.from_template(QUERY_STEP_PROMPT)
        chain = (
            {"question": RunnablePassthrough(), "context": lambda _: context}
            | prompt
            | self.llm
            | StrOutputParser()
        )

        for chunk in chain.stream(query):
            yield chunk

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
#
#     test = GenerationIntegrationModule()
#     print(test.query_router("最近有点缺铁，缺维生素了，给我推荐一下一周的一日三餐"))