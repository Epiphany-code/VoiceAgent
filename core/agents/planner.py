from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from core.llm import get_llm
from core.state import AgentState
from core.agents.weather import ask_weather
from core.agents.schedule import ask_schedule

# 导出工具列表供 Workflow 使用
PLANNER_TOOLS = [ask_weather, ask_schedule]

def filter_recent_messages(messages, turns=5):
    """
    保留最近 N 轮对话作为短期记忆。
    """
    human_indices = [i for i, m in enumerate(messages) if m.type == "human"]
    if len(human_indices) <= turns:
        return messages
    start_index = human_indices[-turns]
    return messages[start_index:]

def planner_node(state: AgentState):
    # 使用 Planner 专用模型配置
    llm = get_llm(agent_name="planner")
    
    # 绑定工具
    llm_with_tools = llm.bind_tools(PLANNER_TOOLS)
    
    # System Prompt
    system_prompt = """
        你是 VoiceAgent 的核心规划师 (Planner)。  
        你的职责是根据用户需求，调度工具 (ask_weather, ask_schedule) 并生成逻辑清晰、信息准确的回复。  

        ## 输出
        - 保证内容的准确性和完整性。  

        ## 核心能力
        - 意图识别：  
            - 查天气：提取地点日期 -> ask_weather -> 返回结果。  
            - 做规划：提取地点日期 -> ask_weather (必须先做) -> 拿到天气 -> ask_schedule -> 汇总建议。  

        ## 决策原则
        - 必须串行：先查天气，根据天气结果再查行程。禁止盲目并发。  
        - 参数透传：调用 ask_schedule 时，weather_info 必须填入真实的 ask_weather 返回值。  
        - 拒绝废话：需要调工具时，直接输出 Tool Call，不要说 "好的我去查"。  

        ## 异常处理
        - 如果工具返回错误（如无法获取天气），请诚实地告诉用户，并尝试给出通用建议。
        """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="recent_messages"),
    ])
    
    chain = prompt | llm_with_tools
    
    recent_messages = filter_recent_messages(state["messages"], turns=5)
    
    response = chain.invoke({
        "recent_messages": recent_messages
    })
    
    return {"messages": [response]}