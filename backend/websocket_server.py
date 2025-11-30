import asyncio
import logging
import json
import time
import re
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from core.workflow import create_workflow
from audio.asr import DoubaoASR
from audio.tts import DoubaoTTS
from langchain_core.messages import HumanMessage, AIMessage

router = APIRouter()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("backend.ws")

# --- TTS 流式 ---
class StreamTTSHandler:
    def __init__(self, tts_worker: DoubaoTTS, websocket: WebSocket):
        self.tts_worker = tts_worker
        self.websocket = websocket
        
        self.text_queue = asyncio.Queue()
        self.audio_stream_queue = asyncio.Queue()
        
        self.buffer = ""
        self.processor_task = None
        self.sender_task = None
        # 追踪后台预取任务，以便打断时清理
        self.prefetch_tasks = set()
        
        self.is_first_chunk = True 
        
        # 强标点：句号、问号、感叹号 (用于首句切分)
        self.sentence_pattern = re.compile(r'[。！？!?\n]')
        # 弱标点：逗号、分号 (用于后续切分)
        self.comma_pattern = re.compile(r'[，,;；]')

    async def start(self):
        self.processor_task = asyncio.create_task(self._text_processing_loop())
        self.sender_task = asyncio.create_task(self._audio_sending_loop())

    async def feed_token(self, token: str):
        await self.text_queue.put(token)

    async def stop(self):
        """正常结束：等待所有缓冲播放完毕"""
        await self.text_queue.put(None)
        if self.processor_task: await self.processor_task
        if self.sender_task: await self.sender_task

    async def cancel(self):
        """暴力打断：立即取消所有后台任务"""
        # 1. 停止主循环
        if self.processor_task and not self.processor_task.done():
            self.processor_task.cancel()
        if self.sender_task and not self.sender_task.done():
            self.sender_task.cancel()
            
        # 2. 停止所有正在进行的 TTS 预取任务
        for task in list(self.prefetch_tasks):
            if not task.done():
                task.cancel()
        self.prefetch_tasks.clear()

        # 3. 清空队列
        while not self.text_queue.empty(): self.text_queue.get_nowait()
        while not self.audio_stream_queue.empty(): self.audio_stream_queue.get_nowait()

    async def _text_processing_loop(self):
        try:
            while True:
                token = await self.text_queue.get()
                
                if token is None:
                    if self.buffer.strip():
                        await self._trigger_tts_prefetch(self.buffer)
                    await self.audio_stream_queue.put(None)
                    break
                
                self.buffer += token
                
                should_split = False
                split_idx = -1
                
                # --- 防爆音 ---
                if self.is_first_chunk:
                    # 策略：首句必须遇到【强标点】才切分。
                    # 哪怕 "你好！" 很短，因为有感叹号，TTS 引擎知道这是句尾，会处理好衰减。
                    # 如果是 "你好，我是..."，在 "好" 后面切分会导致 "好" 的尾音被截断或产生杂音。
                    # 所以首句绝对不通过逗号切分，必须等句号/问号/感叹号。
                    match = self.sentence_pattern.search(self.buffer)
                    if match:
                        split_idx = match.end()
                        should_split = True
                    # 只有当缓冲区积压太长（超过 50 字）还没遇到强标点时，才被迫用逗号切分
                    # 这是为了防止首字延迟过大
                    elif len(self.buffer) > 50:
                        c_match = self.comma_pattern.search(self.buffer)
                        if c_match:
                            split_idx = c_match.end()
                            should_split = True
                        else:
                            # 实在连逗号都没有，才强行切分
                            split_idx = len(self.buffer)
                            should_split = True
                else:
                    # 后续句子可以放宽，允许逗号切分，保证流式体验
                    match = self.sentence_pattern.search(self.buffer)
                    if match:
                        split_idx = match.end()
                        should_split = True
                    elif len(self.buffer) > 20: # 后续句子阈值可以低一点
                        c_match = self.comma_pattern.search(self.buffer)
                        if c_match:
                            split_idx = c_match.end()
                            should_split = True
                        else:
                            split_idx = len(self.buffer)
                            should_split = True

                if should_split:
                    text_segment = self.buffer[:split_idx]
                    self.buffer = self.buffer[split_idx:]
                    if text_segment.strip():
                        await self._trigger_tts_prefetch(text_segment)
                        self.is_first_chunk = False
        except asyncio.CancelledError:
            pass # 允许被取消

    async def _trigger_tts_prefetch(self, text):
        segment_data_queue = asyncio.Queue()
        await self.audio_stream_queue.put(segment_data_queue)
        
        # 创建任务并追踪
        task = asyncio.create_task(self._fetch_tts_data(text, segment_data_queue))
        self.prefetch_tasks.add(task)
        task.add_done_callback(self.prefetch_tasks.discard)

    async def _fetch_tts_data(self, text, data_queue):
        try:
            async for chunk in self.tts_worker.synthesize_stream(text):
                await data_queue.put(chunk)
        except Exception as e:
            logger.error(f"TTS Gen Error: {e}")
        finally:
            await data_queue.put(None)

    async def _audio_sending_loop(self):
        try:
            while True:
                segment_queue = await self.audio_stream_queue.get()
                if segment_queue is None: break 
                
                while True:
                    chunk = await segment_queue.get()
                    if chunk is None: break
                    
                    if self.websocket.client_state == WebSocketState.CONNECTED:
                        await self.websocket.send_bytes(chunk)
                    else:
                        return
        except asyncio.CancelledError:
            pass


async def consume_and_stream_asr(websocket: WebSocket, asr_worker: DoubaoASR, audio_queue: asyncio.Queue):
    """ASR 后台任务"""
    final_text = ""
    async def audio_gen():
        while True:
            chunk = await audio_queue.get()
            if chunk is None: break
            yield chunk

    try:
        async for text in asr_worker.recognize_stream(audio_gen()):
            final_text = text
            await websocket.send_json({"type": "chat_user_temp", "text": final_text})
    except Exception as e:
        logger.error(f"ASR Task Error: {e}")
    
    return final_text

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    asr_worker = DoubaoASR()
    tts_worker = DoubaoTTS()
    agent_app = create_workflow()
    
    greeting = "你好！我是你的智能行程规划助理。请告诉我你想去哪里，或者查天气。"
    await websocket.send_json({"type": "chat_agent_start", "latency": "0ms"})
    await websocket.send_json({"type": "chat_agent_stream", "text": greeting})
    
    audio_queue = None
    asr_task = None
    is_recording = False
    
    # [新增] 任务管理器：当前正在运行的 Agent 思考/说话任务
    current_agent_task = None

    async def cancel_current_agent():
        """打断逻辑：取消当前正在进行的 Agent 任务"""
        nonlocal current_agent_task
        if current_agent_task and not current_agent_task.done():
            logger.info("检测到新指令，正在打断上一轮对话...")
            current_agent_task.cancel()
            try:
                await current_agent_task
            except asyncio.CancelledError:
                pass
            current_agent_task = None

    try:
        while True:
            if websocket.client_state == WebSocketState.DISCONNECTED: break
            try:
                message = await websocket.receive()
            except RuntimeError: break 
            
            if "text" in message:
                data = json.loads(message["text"])
                cmd = data.get("type")
                
                if cmd == "start_recording":
                    # [打断] 用户开始说话，立即停止系统当前的废话
                    await cancel_current_agent()
                    
                    is_recording = True
                    audio_queue = asyncio.Queue()
                    asr_task = asyncio.create_task(consume_and_stream_asr(websocket, asr_worker, audio_queue))
                    logger.info("Recording Started.")
                        
                elif cmd == "stop_recording":
                    if is_recording and audio_queue:
                        is_recording = False
                        await audio_queue.put(None)
                        await websocket.send_json({"type": "status", "state": "recognizing"})
                        
                        user_text = ""
                        if asr_task:
                            user_text = await asr_task
                            asr_task = None
                        
                        logger.info(f"User Input: {user_text}")

                        if not user_text:
                            await websocket.send_json({"type": "status", "state": "idle"})
                            continue
                            
                        await websocket.send_json({"type": "chat_user", "text": user_text})
                        
                        # [异步启动] 开启新一轮 Agent 任务，不阻塞主循环
                        current_agent_task = asyncio.create_task(
                            run_agent_cycle_v2(websocket, agent_app, tts_worker, user_text)
                        )

                elif cmd == "text_input":
                    user_text = data.get("text", "")
                    if user_text:
                        # [打断] 用户输入文本，也视为打断
                        await cancel_current_agent()
                        # [异步启动]
                        current_agent_task = asyncio.create_task(
                            run_agent_cycle_v2(websocket, agent_app, tts_worker, user_text)
                        )

            elif "bytes" in message:
                if is_recording and audio_queue:
                    await audio_queue.put(message["bytes"])

    except WebSocketDisconnect: pass
    except Exception as e: logger.error(f"WS Error: {e}")
    finally:
        # 清理所有任务
        if audio_queue: await audio_queue.put(None)
        if asr_task: asr_task.cancel()
        await cancel_current_agent()
        try: await websocket.close()
        except: pass

async def run_agent_cycle_v2(websocket, agent_app, tts_worker, user_text):
    """
    Agent 主循环。现在可以被 cancel_current_agent() 随时取消。
    """
    await websocket.send_json({"type": "status", "state": "thinking"})
    
    start_time = time.perf_counter()
    first_token_received = False
    thread_id = "demo_session"
    
    tts_handler = StreamTTSHandler(tts_worker, websocket)
    await tts_handler.start()
    
    try:
        async for event in agent_app.astream_events(
            {"messages": [HumanMessage(content=user_text)]},
            config={"configurable": {"thread_id": thread_id}}, 
            version="v2"
        ):
            event_type = event["event"]
            metadata = event.get("metadata", {})
            node_name = metadata.get("langgraph_node", "")
            
            if event_type == "on_chat_model_stream" and node_name == "talker":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    token = chunk.content
                    if not first_token_received:
                        ttft = (time.perf_counter() - start_time) * 1000
                        logger.info(f"[Latency] Real TTFT: {ttft:.2f}ms")
                        await websocket.send_json({
                            "type": "chat_agent_start",
                            "latency": f"{ttft:.0f}ms"
                        })
                        await websocket.send_json({"type": "status", "state": "speaking"})
                        first_token_received = True
                    
                    await websocket.send_json({"type": "chat_agent_stream", "text": token})
                    await tts_handler.feed_token(token)

            elif event_type == "on_tool_start":
                tool_name = event["name"]
                tool_input = event["data"].get("input")
                display_name = f"调用工具: {tool_name}"
                await websocket.send_json({
                    "type": "thought", 
                    "name": display_name,
                    "content": f"输入参数: {json.dumps(tool_input, ensure_ascii=False)}"
                })
                
            elif event_type == "on_chat_model_end" and node_name == "planner":
                output_msg = event["data"]["output"]
                if output_msg.content:
                     await websocket.send_json({
                        "type": "thought", 
                        "name": "规划器思考",
                        "content": output_msg.content
                    })
        
        # 正常结束
        await tts_handler.stop()
        await websocket.send_json({"type": "status", "state": "idle"})

    except asyncio.CancelledError:
        # [关键] 任务被取消时的处理逻辑
        logger.info("Agent 任务被中断")
        await tts_handler.cancel() # 立即停止 TTS 发送
        await websocket.send_json({"type": "status", "state": "idle"})
        raise # 重新抛出，让 asyncio 知道任务已取消

    except Exception as e:
        logger.error(f"Agent Cycle Error: {e}")
        if not first_token_received:
             await websocket.send_json({"type": "chat_agent_start", "latency": "Error"})
             await websocket.send_json({"type": "chat_agent_stream", "text": "系统处理出错。"})
        await tts_handler.cancel()
        await websocket.send_json({"type": "status", "state": "idle"})