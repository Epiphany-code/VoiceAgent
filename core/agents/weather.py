import os
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from core.tools.bridge import MCPBridge
from core.llm import get_llm

# Path to weather server
# 假设 weather_server.py 在项目根目录的 tools/ 文件夹下
WEATHER_SERVER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../tools/weather_server.py"))

@tool
async def ask_weather(query: str) -> str:
    """
    咨询气象专家。输入你想查询的天气问题（如：南京未来三天天气）。
    返回自然语言的天气总结。
    """
    # 启动 MCP Bridge
    async with MCPBridge(WEATHER_SERVER_PATH) as bridge:
        # 获取 MCP 工具 (get_weather 等)
        tools = await bridge.get_langchain_tools()
        temp = float(os.getenv("MODEL_WEATHER_TEMP", 0.1))

        llm = get_llm(temperature=temp)
        
        # 创建微型 ReAct Agent (Weather Expert)
        # 这个 Agent 负责思考如何使用 MCP 工具来回答 query
        agent = create_react_agent(llm, tools)
        
        # 执行 Agent
        # 注意：这里是独立的 Agent 执行流，它的记忆是临时的 (Local Memory)
        result = await agent.ainvoke({"messages": [("user", query)]})
        
        # 返回最终生成的回复 (Last message content)
        return result["messages"][-1].content
