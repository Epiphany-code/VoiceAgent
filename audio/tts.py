import asyncio
import json
import uuid
import gzip
import logging
import websockets
import os
from typing import AsyncGenerator

logger = logging.getLogger("audio.tts")

class DoubaoTTS:
    def __init__(self):
        self.appid = os.getenv("VOLC_APPID")
        self.token = os.getenv("VOLC_ACCESS_TOKEN")
        self.cluster = os.getenv("VOLC_TTS_CLUSTER", "volcano_tts")
        self.voice_type = os.getenv("VOLC_TTS_VOICE_TYPE", "zh_female_cancan_mars_bigtts")
        self.url = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        [V1 协议] 文本转语音流式合成。
        """
        headers = {
            "Authorization": f"Bearer;{self.token}"
        }
        
        req_id = str(uuid.uuid4())
        payload = {
            "app": {
                "appid": self.appid,
                "token": "access_token",
                "cluster": self.cluster
            },
            "user": {"uid": "user_001"},
            "audio": {
                "voice_type": self.voice_type,
                "encoding": "pcm",
                "speed_ratio": 1.0,
                # 源头音量设为 1.0，不要过大，避免削顶
                "volume_ratio": 1.0, 
                "pitch_ratio": 1.0,
                "rate": 24000 
            },
            "request": {
                "reqid": req_id,
                "text": text,
                "operation": "submit"
            }
        }

        try:
            async with websockets.connect(self.url, additional_headers=headers) as ws:
                header = b'\x11\x10\x11\x00' # Gzip
                payload_bytes = gzip.compress(json.dumps(payload).encode('utf-8'))
                payload_size = len(payload_bytes).to_bytes(4, 'big')
                
                await ws.send(header + payload_size + payload_bytes)
                
                while True:
                    msg = await ws.recv()
                    if len(msg) < 4: continue
                    
                    msg_type = (msg[1] >> 4) & 0x0F
                    compression_type = msg[2] & 0x0F
                    
                    if msg_type == 0xB: # 音频响应
                        # 格式: Header(4) + Seq(4) + Size(4) + Audio
                        if len(msg) < 12: continue
                        
                        seq = int.from_bytes(msg[4:8], 'big', signed=True)
                        payload_size = int.from_bytes(msg[8:12], 'big')
                        
                        if len(msg) < 12 + payload_size: continue
                        audio_data = msg[12 : 12 + payload_size]
                        
                        if compression_type == 0x1: # Gzip
                            audio_data = gzip.decompress(audio_data)
                        
                        if audio_data:
                            yield audio_data
                            
                        if seq < 0: # 流结束
                            break
                            
                    elif msg_type == 0xF: # 错误响应
                        error_size = int.from_bytes(msg[8:12], 'big')
                        error_data = msg[12 : 12 + error_size]
                        if compression_type == 0x1:
                            error_data = gzip.decompress(error_data)
                        logger.error(f"TTS 服务端错误: {error_data.decode('utf-8', errors='ignore')}")
                        break
                        
        except Exception as e:
            logger.error(f"TTS 连接异常: {e}")