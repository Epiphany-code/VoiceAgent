from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from core.llm import get_llm
from typing import Optional

@tool
def ask_schedule(location: str, date: str, weather_info: str, preferences: str = "") -> str:
    """
    咨询行程专家。
    """
    missing = []
    if not location: missing.append("目的地")
    if not date: missing.append("日期")
    if not weather_info: missing.append("天气")
    if missing: return f"缺失信息：{', '.join(missing)}"

    llm = get_llm(agent_name="schedule")
    
    # 优化2：精简 Prompt，要求“大纲式”输出，减少 Token 数量，从而减少生成时间
    system_prompt = """
    你是行程规划专家。根据条件设计简要行程。
    
    输入：
    - 地点: {location}, 时间: {date}, 天气: {weather_info}, 偏好: {preferences}
    
    要求：
    1. 必须根据天气调整（雨天室内，晴天室外）。
    2. 仅列出 3-4 个核心景点，不要长篇大论。
    3. 输出格式极其简洁，例如："上午：xxx；下午：xxx；晚上：xxx"。
    4. 不要任何开场白和结束语，直接给方案。
    """
    
    prompt = ChatPromptTemplate.from_template(system_prompt)
    chain = prompt | llm
    
    # 这一步是同步阻塞的，生成的字越少，阻塞时间越短
    response = chain.invoke({
        "location": location, "date": date, "weather_info": weather_info, "preferences": preferences
    })
    
    return response.content