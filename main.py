import os
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.websocket_server import router as websocket_router
from backend.config_api import router as config_router
from dotenv import load_dotenv

# 3. 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 加载环境变量
load_dotenv()

app = FastAPI(title="VoiceAgent", description="LangGraph + 豆包语音智能助理")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 WebSocket 路由
app.include_router(websocket_router)

# 注册配置 API 路由
app.include_router(config_router, prefix="/api/config", tags=["config"])

# favicon 路由（防止 404 日志）
@app.get("/favicon.ico", include_in_schema=False)
async def favicon_404():
    return {}

# 挂载静态文件（前端页面）
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    logger = logging.getLogger("main")
    logger.info("VoiceAgent 服务已启动，访问地址：http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)