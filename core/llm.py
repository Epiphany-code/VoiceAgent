import os
import time
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

# 加载 .env 环境变量
load_dotenv()

logger = logging.getLogger("core.llm")

class LoggingCallbackHandler(BaseCallbackHandler):
    """
    跟踪大模型延迟（首字延迟TTFT和总耗时）。
    """
    def __init__(self, model_name):
        self.model_name = model_name
        self.start_time = 0
        self.first_token_time = 0

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.start_time = time.time()
        self.first_token_time = 0

    def on_llm_new_token(self, token: str, **kwargs):
        if self.first_token_time == 0:
            self.first_token_time = time.time()
            ttft = (self.first_token_time - self.start_time) * 1000
            logger.info(f"[{self.model_name}] 首字延迟TTFT: {ttft:.2f} ms")

    def on_llm_end(self, response: LLMResult, **kwargs):
        end_time = time.time()
        total_duration = (end_time - self.start_time) * 1000

        logger.info(f"[{self.model_name}] 生成结束，总推理时长: {total_duration:.2f} ms")

def get_llm(model_name: str = None, temperature: float = 0.1, streaming: bool = True):
    """获取配置好的 LLM 实例"""
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL")
    
    target_model = model_name or os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen2.5-32B-Instruct")

    if not api_key:
        raise ValueError("请在 .env 中配置 SILICONFLOW_API_KEY")

    llm = ChatOpenAI(
        model=target_model,
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=temperature,
        streaming=streaming,
        callbacks=[LoggingCallbackHandler(target_model)]
    )
    return llm