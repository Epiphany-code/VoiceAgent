"""
配置管理器 - 单例模式，统一管理所有模型配置

支持多个提供商（SiliconFlow、本地模型），每个 Agent 可以独立选择提供商和模型。
"""
import os
import re
from dataclasses import dataclass
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import logging

logger = logging.getLogger("core.config_manager")

load_dotenv()


@dataclass
class ProviderConfig:
    """提供商配置"""
    api_key: str
    base_url: str


@dataclass
class AgentConfig:
    """Agent 模型配置"""
    provider: str  # "siliconflow" 或 "local"
    model: str
    temperature: float
    max_tokens: int


class ConfigManager:
    """单例配置管理器"""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config_cache: Dict[str, Any] = {}
        self._env_file_path = self._find_env_file()
        self._reload_config()

    def _find_env_file(self) -> str:
        """查找 .env 文件路径"""
        # 从当前文件位置向上查找
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        env_path = os.path.join(project_root, ".env")
        return env_path

    def _reload_config(self):
        """重新加载配置到缓存"""
        self._config_cache = {
            "siliconflow": ProviderConfig(
                api_key=os.getenv("SILICONFLOW_API_KEY", ""),
                base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
            ),
            "local": ProviderConfig(
                api_key=os.getenv("LOCAL_API_KEY", ""),
                base_url=os.getenv("LOCAL_BASE_URL", "http://localhost:1234/v1")
            )
        }

        # Agent 配置
        agents = ["planner", "schedule", "weather", "talker", "default"]
        for agent in agents:
            agent_upper = agent.upper()
            self._config_cache[f"agent_{agent}"] = AgentConfig(
                provider=os.getenv(f"MODEL_{agent_upper}_PROVIDER", "siliconflow"),
                model=os.getenv(f"MODEL_{agent_upper}", "Qwen/Qwen2.5-32B-Instruct"),
                temperature=float(os.getenv(f"MODEL_{agent_upper}_TEMP", "0.1")),
                max_tokens=int(os.getenv(f"MODEL_{agent_upper}_MAX_TOKENS", "2048"))
            )

    def get_provider_config(self, provider_name: str) -> ProviderConfig:
        """
        获取指定提供商的配置

        Args:
            provider_name: "siliconflow" 或 "local"

        Returns:
            ProviderConfig 对象
        """
        return self._config_cache.get(provider_name, self._config_cache["siliconflow"])

    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """
        获取指定 Agent 的模型配置

        Args:
            agent_name: Agent 名称，如 "planner", "schedule", "weather", "talker"

        Returns:
            AgentConfig 对象
        """
        key = f"agent_{agent_name.lower()}"
        if key not in self._config_cache:
            return self._config_cache["agent_default"]
        return self._config_cache[key]

    def get_all_config(self) -> Dict[str, Any]:
        """
        获取所有配置（供 API 使用）

        Returns:
            包含所有配置的字典
        """
        return {
            "providers": {
                "siliconflow": {
                    "api_key": self._config_cache["siliconflow"].api_key,
                    "base_url": self._config_cache["siliconflow"].base_url
                },
                "local": {
                    "api_key": self._config_cache["local"].api_key,
                    "base_url": self._config_cache["local"].base_url
                }
            },
            "agents": {
                agent: {
                    "provider": config.provider,
                    "model": config.model,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens
                }
                for agent, config in [
                    ("planner", self._config_cache["agent_planner"]),
                    ("schedule", self._config_cache["agent_schedule"]),
                    ("weather", self._config_cache["agent_weather"]),
                    ("talker", self._config_cache["agent_talker"]),
                    ("default", self._config_cache["agent_default"])
                ]
            }
        }

    def update_config(self, updates: Dict[str, str]) -> bool:
        """
        更新配置并写入 .env 文件

        Args:
            updates: 配置更新字典，key 为配置名，value 为新值

        Returns:
            是否更新成功
        """
        try:
            # 读取现有 .env 文件
            if not os.path.exists(self._env_file_path):
                logger.warning(f"配置文件不存在: {self._env_file_path}")
                return False

            with open(self._env_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 更新配置行
            updated_lines = []
            config_pattern = re.compile(r'^([A-Z_]+)\s*=\s*(.*)$')

            # 记录已更新的键
            updated_keys = set()

            for line in lines:
                match = config_pattern.match(line.strip())
                if match:
                    key = match.group(1)
                    if key in updates:
                        # 更新此行
                        value = updates[key]
                        # 如果值包含特殊字符，用引号包裹
                        if value and (' ' in value or '"' in value or "'" in value):
                            value = f'"{value}"'
                        updated_lines.append(f"{key}={value}\n")
                        updated_keys.add(key)
                    else:
                        updated_lines.append(line)
                else:
                    # 保留注释和空行
                    updated_lines.append(line)

            # 添加新的配置项（如果之前不存在）
            for key, value in updates.items():
                if key not in updated_keys:
                    # 如果值包含特殊字符，用引号包裹
                    if value and (' ' in value or '"' in value or "'" in value):
                        value = f'"{value}"'
                    updated_lines.append(f"{key}={value}\n")

            # 写回文件
            with open(self._env_file_path, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)

            # 重新加载配置
            self._reload_config()

            logger.info(f"配置已更新: {list(updates.keys())}")
            return True

        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False


# 全局单例实例
config_manager = ConfigManager()
