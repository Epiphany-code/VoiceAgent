import os
import time
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from core.config_manager import config_manager

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

def get_llm(
    agent_name: str = None,
    model_name: str = None,
    temperature: float = None,
    max_tokens: int = None,
    streaming: bool = True
):
    """
    获取配置好的 LLM 实例

    Args:
        agent_name: Agent 名称（如 "planner", "schedule", "weather", "talker"）
                     如果提供，将从配置管理器获取该 Agent 的完整配置
        model_name: 模型名称（如果不提供且未指定 agent_name，使用默认配置）
        temperature: 温度参数（如果不提供且未指定 agent_name，使用默认值 0.1）
        max_tokens: 最大 token 数（如果不提供且未指定 agent_name，使用默认值 2048）
        streaming: 是否启用流式输出

    Returns:
        ChatOpenAI 实例
    """
    # 如果指定了 agent_name，从配置管理器获取完整配置
    if agent_name:
        agent_config = config_manager.get_agent_config(agent_name)
        provider_config = config_manager.get_provider_config(agent_config.provider)

        target_model = model_name or agent_config.model
        target_temp = temperature if temperature is not None else agent_config.temperature
        target_max_tokens = max_tokens if max_tokens is not None else agent_config.max_tokens
        api_key = provider_config.api_key
        base_url = provider_config.base_url
    else:
        # 向后兼容：使用原有的环境变量方式
        api_key = os.getenv("SILICONFLOW_API_KEY")
        base_url = os.getenv("SILICONFLOW_BASE_URL")
        target_model = model_name or os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen2.5-32B-Instruct")
        target_temp = temperature if temperature is not None else 0.1
        target_max_tokens = max_tokens if max_tokens is not None else 2048

    # API Key 对于本地模型是可选的，允许为空字符串
    # ChatOpenAI 会正确处理空的 API Key

    llm = ChatOpenAI(
        model=target_model,
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=target_temp,
        max_tokens=target_max_tokens,
        streaming=streaming,
        callbacks=[LoggingCallbackHandler(target_model)]
    )
    return llm