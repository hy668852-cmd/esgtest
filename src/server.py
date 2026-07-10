import json
import logging

import cv2
from xiaozhi_sdk import XiaoZhiWebsocket

from src.config import OTA_URL

logger = logging.getLogger(__name__)


class XiaoZhiServer(object):
    def __init__(self, pc):
        self.pc = pc
        self.channel = pc.createDataChannel("chat")
        self.server = None

    def safe_send(self, data):
        """安全发送消息到数据通道，检查通道状态"""
        # 检查数据通道状态是否为 "open"
        if self.channel.readyState == "open":
            self.channel.send(data)
        else:
            logger.warning(
                "数据通道未打开，无法发送消息 [%s %s] 状态: %s",
                self.pc.mac_address,
                self.pc.client_ip,
                self.channel.readyState,
            )

    async def message_handler_callback(self, message):
        logger.info("Received message: %s %s %s", self.pc.mac_address, self.pc.client_ip, message)
        if message["type"] == "websocket" and message["state"] == "close":
            await self.server.close()
            self.server = None

        self.safe_send(json.dumps(message, ensure_ascii=False))
        if message["type"] == "llm" and hasattr(self.pc, "video_track"):
            self.pc.video_track.set_emoji(message["text"])

    async def start(self):
        self.server = XiaoZhiWebsocket(
            self.message_handler_callback,
            ota_url=OTA_URL,
            audio_sample_rate=48000,
            audio_channels=2,
            audio_frame_duration=20,
        )
        await self.server.set_mcp_tool(self.mcp_tool_func())
        await self.server.init_connection(self.pc.mac_address)

    def mcp_tool_func(self):
        def tool_set_volume(data):
            self.safe_send(json.dumps({"type": "tool", "text": "set_volume", "value": data["volume"]}))
            return "", False

        def tool_open_tab(data):
            self.safe_send(json.dumps({"type": "tool", "text": "open_tab", "value": data["url"]}))
            return "", False

        def tool_stop_music(data):
            self.safe_send(json.dumps({"type": "tool", "text": "stop_music"}))
            return "", False

        def tool_get_device_status(data):
            return (
                json.dumps(
                    {
                        "audio_speaker": {"volume": 100},
                        # 'screen': {'brightness': 75, 'theme': 'light'},
                        # 'network': {'type': 'wifi', 'ssid': 'wifi名称', 'signal': 'strong'}
                    }
                ),
                False,
            )

        async def tool_take_photo(data):
            img_obj = self.server.video_frame.to_ndarray(format="bgr24")
            # 直接使用 OpenCV 编码图片
            _, img_byte = cv2.imencode(".jpg", img_obj)
            img_byte = img_byte.tobytes()
            return await self.server.async_analyze_image(img_byte, data.get("question", "请描述这张图片"))

        from xiaozhi_sdk.utils.mcp_tool import (
            get_device_status,
            open_tab,
            play_custom_music,
            search_custom_music,
            set_volume,
            stop_music,
            take_photo,
        )

        take_photo["tool_func"] = tool_take_photo
        take_photo["is_async"] = True

        get_device_status["tool_func"] = tool_get_device_status
        set_volume["tool_func"] = tool_set_volume
        open_tab["tool_func"] = tool_open_tab
        stop_music["tool_func"] = tool_stop_music

        return [
            take_photo,
            get_device_status,
            set_volume,
            take_photo,
            open_tab,
            stop_music,
            search_custom_music,
            play_custom_music,
        ]
