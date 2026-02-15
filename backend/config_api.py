"""
配置管理 API 端点

提供配置的读取、更新、测试连接等接口。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
from core.config_manager import config_manager
import httpx

router = APIRouter()


class ConfigUpdateRequest(BaseModel):
    """配置更新请求"""
    updates: Dict[str, str]


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    provider: str  # "siliconflow" 或 "local"


@router.get("/")
async def get_all_config():
    """
    获取所有配置

    Returns:
        包含所有配置的 JSON 响应
    """
    try:
        config = config_manager.get_all_config()
        return {
            "success": True,
            "data": config,
            "message": "配置获取成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.get("/agent/{agent_name}")
async def get_agent_config(agent_name: str):
    """
    获取指定 Agent 的配置

    Args:
        agent_name: Agent 名称

    Returns:
        包含 Agent 配置的 JSON 响应
    """
    try:
        config = config_manager.get_agent_config(agent_name)
        return {
            "success": True,
            "data": {
                "provider": config.provider,
                "model": config.model,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens
            },
            "message": f"Agent {agent_name} 配置获取成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Agent 配置失败: {str(e)}")


@router.get("/provider")
async def get_provider_config():
    """
    获取所有提供商配置

    Returns:
        包含所有提供商配置的 JSON 响应
    """
    try:
        config = config_manager.get_all_config()
        return {
            "success": True,
            "data": config["providers"],
            "message": "提供商配置获取成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取提供商配置失败: {str(e)}")


@router.post("/update")
async def update_config(request: ConfigUpdateRequest):
    """
    更新配置

    Args:
        request: 包含配置更新的请求体

    Returns:
        更新结果的 JSON 响应
    """
    try:
        success = config_manager.update_config(request.updates)
        if success:
            return {
                "success": True,
                "message": "配置更新成功，请重启服务以使配置生效"
            }
        else:
            raise HTTPException(status_code=500, detail="配置更新失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.post("/test")
async def test_connection(request: TestConnectionRequest):
    """
    测试模型提供商连接

    Args:
        request: 包含提供商名称的请求体

    Returns:
        测试结果的 JSON 响应
    """
    try:
        provider_config = config_manager.get_provider_config(request.provider)

        # 测试连接：调用模型的 /models 端点
        # API Key 是可选的，只有配置了才添加到请求头
        headers = {"Content-Type": "application/json"}
        if provider_config.api_key:
            headers["Authorization"] = f"Bearer {provider_config.api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{provider_config.base_url.rstrip('/')}/models",
                headers=headers
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"{request.provider} 连接成功",
                    "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else None
                }
            else:
                return {
                    "success": False,
                    "message": f"连接失败: HTTP {response.status_code}",
                    "detail": response.text
                }

    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "连接超时，请检查 API 地址是否正确"
        }
    except httpx.ConnectError:
        return {
            "success": False,
            "message": "连接被拒绝，请确保本地模型服务已启动"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试连接失败: {str(e)}")
