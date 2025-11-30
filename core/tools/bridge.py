import sys
from typing import List, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import tool, StructuredTool
from pydantic import create_model

class MCPBridge:
    """
    负责管理与 MCP Server 的连接，并将 MCP 工具转换为 LangChain 工具
    """
    def __init__(self, server_script_path: str):
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script_path],
            env=None
        )
        self.session = None
        self.client_ctx = None

    async def __aenter__(self):
        # 建立连接上下文
        self.client_ctx = stdio_client(self.server_params)
        read, write = await self.client_ctx.__aenter__()
        
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.__aexit__(exc_type, exc_val, exc_tb)
        if self.client_ctx:
            await self.client_ctx.__aexit__(exc_type, exc_val, exc_tb)

    async def get_langchain_tools(self) -> List[StructuredTool]:
        """查询 MCP Server 的能力，并自动转换为 LangChain 工具"""
        if not self.session:
            raise RuntimeError("MCP Bridge not connected. Use 'async with' context.")

        mcp_tools = await self.session.list_tools()
        langchain_tools = []

        for m_tool in mcp_tools.tools:
            # 动态创建工具函数
            async def _dynamic_tool_func(**kwargs):
                # 真正的调用发生在这里
                result = await self.session.call_tool(m_tool.name, arguments=kwargs)
                return result.content[0].text

            # 动态创建参数模型 (Pydantic)
            # 简化处理：目前假设所有参数都是 string，生产环境需要根据 JSON Schema 严格转换
            fields = {k: (str, ...) for k in m_tool.inputSchema.get("properties", {}).keys()}
            InputModel = create_model(f"{m_tool.name}_Input", **fields)

            # 封装为 LangChain Tool
            lc_tool = StructuredTool.from_function(
                func=None,
                coroutine=_dynamic_tool_func, # 关键：这是异步工具
                name=m_tool.name,
                description=m_tool.description or "",
                args_schema=InputModel
            )
            langchain_tools.append(lc_tool)
        
        return langchain_tools
