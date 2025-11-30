# VoiceAgent

VoiceAgent 是一个全栈语音智能助理演示项目，旨在展示极低延迟的语音交互体验与强大的多智能体协同能力。

项目采用了 LangGraph 进行智能体编排，通过 WebSocket 实现全双工实时通信，利用 MCP (Model Context Protocol) 接入外部工具，并针对语音交互场景进行了深度的首字延迟 (TTFT) 优化和音频流式播放防爆音处理。

## 核心特性

### 分层多智能体架构 (HMAS)：

Planner (规划师)：负责意图识别、任务拆解和工具调度。

Talker (润色师)：专注于将逻辑结果转化为自然、有温度的口语脚本，适配 TTS 输出。

### 极致的流式体验：

全链路流式：ASR (语音转文字) -> LLM (思考与生成) -> TTS (文字转语音) 全程流式处理。

并行流水线：后端采用 StreamTTSHandler 实现文本生成与音频合成的并行预取，显著降低等待时间。

打字机效果：前端实时展示系统生成的每一个字符，与语音播放同步。

### 音频处理：

防爆音调度器：前端实现了物理级 PCM 软启动 (Soft Start) 和音频源管理，彻底消除流式播放中的爆裂音和断流杂音。

豆包大模型语音：集成火山引擎 (Volcengine)  ASR 和 TTS 服务。

### 可视化与监控：

前端实时显示 TTFT (首字延迟) 数据。

折叠式展示智能体内部思考过程 (Thought Chain) 和工具调用参数。

## 系统架构

```
graph TD
    User((用户)) <-->|WebSocket (Opus/PCM)| Frontend[前端 (Web Audio API)]
    Frontend <-->|WebSocket| Backend[FastAPI Server]
    
    subgraph "Backend Core"
        Backend --> ASR[豆包 ASR]
        Backend --> Workflow[LangGraph Workflow]
        Backend --> TTS[豆包 TTS]
        
        Workflow --> Planner[Planner Agent]
        Workflow --> Talker[Talker Agent]
        
        Planner <-->|MCP Protocol| WeatherTool[Weather MCP Server]
        Planner <--> ScheduleTool[Schedule Tool]
    end
    
    WeatherTool --> AmapAPI[高德开放平台]
    Workflow --> LLM[SiliconFlow (Qwen)]
```

## 快速开始

### 1. 环境准备

确保已安装 Python 3.10 或更高版本。

```
git clone [https://github.com/yourusername/VoiceAgent.git](https://github.com/yourusername/VoiceAgent.git)
cd VoiceAgent
```

### 2. 安装依赖

```
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 .env 模板并填入您的 API Key：

```
# 在项目根目录创建 .env 文件
touch .env
```

.env 文件内容参考：

```
# ===== SiliconFlow LLM 配置 (用于推理) =====
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
SILICONFLOW_BASE_URL=[https://api.siliconflow.cn/v1](https://api.siliconflow.cn/v1)
SILICONFLOW_MODEL=Qwen/Qwen2.5-32B-Instruct

# ===== 语音服务配置 (火山引擎/豆包) =====
VOLC_APPID=xxxxxxxx
VOLC_ACCESS_TOKEN=xxxxxxxxxxxxxxxx
VOLC_ASR_RESOURCE_ID=volc.bigasr.sauc.duration
VOLC_TTS_CLUSTER=volcano_tts
VOLC_TTS_VOICE_TYPE=zh_female_cancan_mars_bigtts

# ===== 工具配置 (高德地图) =====
AMAP_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. 启动服务

```
python main.py
```

服务启动后，访问浏览器打开：`http://localhost:8000`

## 项目结构

```
VoiceAgent/
├── main.py                  # 程序入口，FastAPI App
├── requirements.txt         # 项目依赖
├── .env                     # 环境变量配置文件
├── static/                  # 前端静态资源
│   └── index.html           # 单页应用 (HTML/CSS/JS)
├── backend/                 # 后端服务
│   └── websocket_server.py  # WebSocket 核心逻辑，流式处理
├── core/                    # 核心 Agent 逻辑
│   ├── workflow.py          # LangGraph 工作流定义
│   ├── state.py             # Agent 状态定义
│   ├── llm.py               # LLM 封装与延迟日志
│   ├── agents/              # 智能体实现
│   │   ├── planner.py       # 规划师
│   │   ├── talker.py        # 润色师
│   │   ├── weather.py       # 天气工具封装
│   │   └── schedule.py      # 行程工具封装
│   └── tools/               # 工具基础设施
│       └── bridge.py        # MCP 协议桥接器
├── audio/                   # 语音服务接口
│   ├── asr.py               # 豆包 ASR 客户端
│   └── tts.py               # 豆包 TTS 客户端
└── tools/                   # 外部工具实现
    ├── weather_server.py    # 基于 MCP 的天气服务
    └── AMap_adcode_citycode.xlsx # 城市编码数据
```

## 交互说明

1. 点击麦克风：开始录音，按钮变为红色。此时可以说话。

2. 再次点击/停止：发送录音，系统开始识别并响应。

3. 打断：在系统回复过程中，再次点击麦克风或输入文字，系统会立即中断当前语音和思考，响应新的指令。

4. 查看日志：点击对话气泡下方的 ▸ 规划器思考 或 ▸ 调用工具 可展开查看 Agent 的思维链。
