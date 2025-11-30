import asyncio
import json
import uuid
import gzip
import logging
import websockets
import struct
import os
from typing import AsyncGenerator

logger = logging.getLogger("audio.asr")

class DoubaoASR:
    def __init__(self):
        self.appid = os.getenv("VOLC_APPID")
        self.token = os.getenv("VOLC_ACCESS_TOKEN")
        self.resource_id = os.getenv("VOLC_ASR_RESOURCE_ID", "volc.bigasr.sauc.duration")
        self.url = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"
        self.sequence = 1

    def _construct_header(self, msg_type, flag, serialization, compression):
        header = bytearray()
        header.append((0b0001 << 4) | 1) # Version=1, HeaderSize=1
        header.append((msg_type << 4) | flag)
        header.append((serialization << 4) | compression)
        header.append(0x00)
        return bytes(header)

    async def recognize_stream(self, audio_generator: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        """
        实时语音识别生成器。
        Yields:
            str: 实时更新的转录文本 (Cumulative text)
        """
        headers = {
            "X-Api-App-Key": self.appid,
            "X-Api-Access-Key": self.token,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Connect-Id": str(uuid.uuid4())
        }

        self.sequence = 1
        # 用于在接收协程和主生成器之间传递文本结果
        text_queue = asyncio.Queue()
        
        # 握手包 Payload
        req_id = str(uuid.uuid4())
        init_payload = {
            "user": {"uid": "user_001"},
            "audio": {
                "format": "pcm", 
                "codec": "raw", 
                "rate": 16000, 
                "bits": 16, 
                "channel": 1, 
                "language": "zh-CN"
            },
            "request": {
                "reqid": req_id, 
                "model_name": "bigmodel", 
                "enable_itn": True, 
                "enable_punc": True, 
                "show_utterances": True, 
                "result_type": "full", 
                "sequence": 1
            }
        }

        try:
            async with websockets.connect(self.url, additional_headers=headers, ping_interval=None) as ws:
                logger.info("ASR 已连接，握手包已发送。")
                
                # 1. 发送握手
                payload_compressed = gzip.compress(json.dumps(init_payload).encode('utf-8'))
                header = self._construct_header(0b0001, 0b0001, 0b0001, 0b0001)
                await ws.send(header + struct.pack('>i', self.sequence) + struct.pack('>I', len(payload_compressed)) + payload_compressed)
                self.sequence += 1

                # 2. 接收任务 (Producer)
                async def receive_loop():
                    try:
                        async for msg in ws:
                            if len(msg) < 4: continue
                            
                            header_size = msg[0] & 0x0f
                            msg_type = msg[1] >> 4
                            flag = msg[1] & 0x0f
                            compression = msg[2] & 0x0f
                            
                            offset = header_size * 4
                            if flag & 0x01: offset += 4 # Skip Sequence
                            
                            if msg_type == 0b1001: # Server Response
                                if len(msg) < offset + 4: continue
                                payload_size = struct.unpack('>I', msg[offset:offset+4])[0]
                                offset += 4
                                payload_data = msg[offset : offset + payload_size]
                                
                                if compression == 0b0001: # GZIP
                                    try: payload_data = gzip.decompress(payload_data)
                                    except: continue
                                
                                try:
                                    resp = json.loads(payload_data)
                                    if 'result' in resp and 'text' in resp['result']:
                                        text = resp['result']['text'].strip()
                                        if text:
                                            # Put cumulative text into queue
                                            await text_queue.put(text)
                                            # logger.debug(f"分段文本: {text}")
                                except: pass
                            elif msg_type == 0b1111: # 错误响应
                                logger.error("ASR 服务端返回错误类型消息")
                                break
                    except Exception as e:
                        logger.error(f"ASR 接收异常: {e}")
                    finally:
                        await text_queue.put(None) # 结束标记

                recv_task = asyncio.create_task(receive_loop())

                # 3. 发送任务 (Producer)
                async def send_loop():
                    try:
                        async for chunk in audio_generator:
                            if not chunk: continue
                            compressed_chunk = gzip.compress(chunk)
                            header = self._construct_header(0b0010, 0b0001, 0b0000, 0b0001)
                            pkg = header + struct.pack('>i', self.sequence) + struct.pack('>I', len(compressed_chunk)) + compressed_chunk
                            await ws.send(pkg)
                            self.sequence += 1
                        
                        # 发送结束包
                        last_header = self._construct_header(0b0010, 0b0011, 0b0000, 0b0001)
                        last_pkg = last_header + struct.pack('>i', -self.sequence) + struct.pack('>I', 0) + gzip.compress(b'')
                        await ws.send(last_pkg)
                        logger.info("ASR 音频发送完成。")
                    except Exception as e:
                        logger.error(f"ASR 发送任务异常: {e}")

                send_task = asyncio.create_task(send_loop())

                # 4. 主循环：将结果 yield 给调用方
                while True:
                    # 等待文本结果
                    text = await text_queue.get()
                    if text is None: # 接收循环结束
                        break
                    yield text
                
                # 等待发送任务确保清理
                try:
                    await send_task
                except: pass

        except Exception as e:
            logger.error(f"ASR 连接异常: {e}")
            yield "" # 出错时返回空字符串