from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from core.state import AgentState
from core.agents.planner import planner_node, PLANNER_TOOLS
from core.agents.talker import talker_node

def create_workflow():
    """
    构建 HMAS (Hierarchical Multi-Agent System) 工作流
    流程: Start -> Planner <-> Tools -> Talker -> End
    """
    workflow = StateGraph(AgentState)
    
    # --- Nodes ---
    # Layer 2: Planner (大脑 - 逻辑规划)
    workflow.add_node("planner", planner_node)
    
    # Layer 3: Experts (工具层)
    workflow.add_node("tools", ToolNode(PLANNER_TOOLS))
    
    # Layer 3.5: Talker (嘴巴 - 语音润色)
    workflow.add_node("talker", talker_node)
    
    # --- Edges ---
    workflow.add_edge(START, "planner")
    
    # Planner 的条件跳转逻辑
    def planner_condition(state):
        # 使用 langgraph 自带的 tools_condition 判断是否有工具调用
        # 如果有工具调用 -> "tools"
        # 如果没有工具调用 (说明 Planner 生成了最终文本) -> "talker" (而不是直接 END)
        if tools_condition(state) == "tools":
            return "tools"
        return "talker"

    workflow.add_conditional_edges(
        "planner",
        planner_condition,
        {
            "tools": "tools",
            "talker": "talker"
        }
    )
    
    # 工具执行完，回 Planner 继续思考
    workflow.add_edge("tools", "planner")
    
    # Talker 润色完，流程结束
    workflow.add_edge("talker", END)
    
    # 初始化内存
    memory = MemorySaver()
    
    # 增加 recursion_limit 防止死循环 (例如 Planner 反复调用同一个工具)
    return workflow.compile(checkpointer=memory)