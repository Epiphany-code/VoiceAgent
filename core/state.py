import operator
from typing import Annotated, List, TypedDict, Optional, Dict, Any
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # messages 列表会在流转中不断追加 (add_messages)
    messages: Annotated[List[BaseMessage], operator.add]
    # 用户偏好
    user_profile: Optional[str]
    # 当前生成的草稿/计划
    current_plan: Optional[str]
    # 计划上下文：存储地点、时间、天气等结构化信息
    plan_context: Annotated[Dict[str, Any], lambda x, y: {**x, **y}]
