from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from core.llm import get_llm
from core.state import AgentState
import re


def filter_think_content(content: str) -> str:
    """
    过滤掉思考内容，只保留有效的回复

    过滤的格式包括：
    - <think> 标签
    - <think>...</think> 代码块
    - Thinking: / 思考： 前缀
    - 【思考】或【Thought】中括号标签
    """
    if not content:
        return content

    # 移除 <think> 标签
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)

    # 移除 Think: / 思考： 开头的行
    lines = content.split('\n')
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('Think:') or stripped.startswith('思考：'):
            continue
        filtered_lines.append(line)
    content = '\n'.join(filtered_lines)

    # 移除连续的空行
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.strip()


def talker_node(state: AgentState):
    """
    Talker Agent: 负责将 Planner 的逻辑输出转化为自然的口语文本 (Speech Script)。
    专门用于 TTS (Text-to-Speech) 前的预处理。
    """
    # Talker 不需要太强的逻辑，需要高情商和自然语言能力
    llm = get_llm(agent_name="talker")

    # 获取 Planner 的最后一条回复
    planner_message = state["messages"][-1]
    original_content = planner_message.content

    # 过滤掉思考内容（同时过滤输入和输出）
    filtered_input = filter_think_content(original_content)

    system_prompt = """
        你是 VoiceAgent 的语音合成润色师。

        ## 你的任务
        将输入的文本重写为适合语音合成的纯文本口语脚本，说得更自然有温度。

        ## 转换规则
        1. 短句优先：长难句拆分为短句，方便听众理解，压缩篇幅。
        2. 去除格式：删除所有 Markdown 符号（如 **加粗**、# 标题、- 列表符）以及表情符号。
        3. 情感注入：根据内容加入适当的语气词（"哇"、"好的"、"没问题"），保持亲切感。
        4. 保持原意：绝对不要篡改 Planner 提供的核心信息（如时间、地点、天气数据）。
        5. 重要：不要输出任何思考过程、推理步骤或 <think> 标签内的内容。直接给出最终的口语化回复。

        ## 示例
        输入: "南京天气：多云，25℃。建议：1. 中山陵；2. 夫子庙。"
        输出: "南京今天是多云天气，气温二十五度，非常舒适。我建议您可以先去中山陵逛逛，晚上再由夫子庙感受秦淮风光。"
        """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{content}")
    ])

    chain = prompt | llm

    # 生成润色后的语音文本
    response = chain.invoke({"content": filtered_input})

    # 我们将 Talker 的回复作为最终回复覆盖或追加
    # 在 AgentState 中，通常最好是追加一个新的 AIMessage
    return {"messages": [response]}
