import asyncio
import json
import logging
import os
import sys

from aiohttp import web
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription

from src.config import DEFAULT_MAC_ADDR, OTA_URL, PORT
from src.config.ice_config import ice_config
from src.server import XiaoZhiServer
from src.track.audio import AudioFaceSwapper
from src.track.video import VideoFaceSwapper

# 设置 logger
logging.basicConfig(
    stream=sys.stdout, level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# 禁用 aioice.ice 模块的日志输出
logging.getLogger("aioice.ice").setLevel(logging.WARNING)

ROOT = os.path.dirname(__file__)


def get_client_ip(request):
    """
    获取客户端真实IP地址
    按优先级尝试多种方式获取，确保在各种部署环境下都能正确获取IP
    """
    # 1. X-Real-IP: 反向代理设置的真实IP (Nginx, Apache等)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip and real_ip != "unknown":
        return real_ip

    # 2. X-Forwarded-For: 代理链中的IP列表，取第一个
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # 可能有多个IP，用逗号分隔，取第一个
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip and first_ip != "unknown":
            return first_ip

    # 3. CF-Connecting-IP: Cloudflare设置的真实IP
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip and cf_ip != "unknown":
        return cf_ip

    # 4. X-Client-IP: 某些代理使用的头
    client_ip = request.headers.get("X-Client-IP")
    if client_ip and client_ip != "unknown":
        return client_ip

    return "unknown"


async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r", encoding="utf-8").read()
    return web.Response(content_type="text/html", text=content)


async def chatv2(request):
    content = open(os.path.join(ROOT, "chatv2.html"), "r", encoding="utf-8").read()
    return web.Response(content_type="text/html", text=content)


async def chat(request):
    content = open(os.path.join(ROOT, "chat.html"), "r", encoding="utf-8").read()
    return web.Response(content_type="text/html", text=content)


async def ice(request):
    """返回ICE服务器配置（使用临时凭证）"""
    client_ip = get_client_ip(request)
    ice_servers_config = ice_config.get_ice_config(client_id=client_ip)
    return web.Response(content_type="application/json", text=json.dumps(ice_servers_config, ensure_ascii=False))


async def offer(request):
    params = await request.json()
    _offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # 使用动态ICE服务器配置
    ice_servers = ice_config.get_server_ice_servers()
    configuration = RTCConfiguration(iceServers=ice_servers, bundlePolicy="max-bundle")
    pc = RTCPeerConnection(configuration=configuration)
    pcs.add(pc)

    # Store client IP in the peer connection object
    # 使用改进的IP获取函数
    pc.client_ip = get_client_ip(request)
    pc.mac_address = params.get("macAddress") or DEFAULT_MAC_ADDR

    await server(pc, _offer)

    return web.Response(
        content_type="application/json",
        text=json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}),
    )


pcs = set()


async def server(pc, offer):
    # Dictionary to store track instances

    xiaozhi = XiaoZhiServer(pc)

    # 监听来自客户端的 DataChannel
    @pc.on("datachannel")
    def on_datachannel(channel):

        @channel.on("message")
        async def on_message(message):
            logger.info("收到客户端消息 [%s %s]: %s", pc.mac_address, pc.client_ip, message)
            if xiaozhi.server is None:
                await xiaozhi.start()

            message = json.loads(message)

            # 处理文字输入消息
            if message.get("type") == "text-input":
                text_content = message.get("text", "")
                if text_content:
                    logger.info("收到文字输入 [%s] (长度:%d): %s", pc.mac_address, len(text_content), text_content[:80])
                    import asyncio
                    import json as _json
                    try:
                        # 1. 中断当前对话
                        await xiaozhi.server.send_abort()
                        await asyncio.sleep(0.3)
                        # 2. 清空输出音频队列
                        xiaozhi.server.output_audio_queue.clear()

                        # 短文本直接用detect发送（唤醒词模式，阈值10个字符）
                        if len(text_content) <= 10:
                            await xiaozhi.server.send_wake_word(text_content)
                            await asyncio.sleep(0.1)
                            await xiaozhi.server.send_silence_audio(1.5)
                            logger.info("短文本发送完成 [%s]", pc.mac_address)
                        else:
                            # 长文本：用TTS转语音后通过音频通道发送
                            await xiaozhi.server.websocket.send(_json.dumps({
                                "session_id": xiaozhi.server.session_id,
                                "type": "listen", "state": "start", "mode": "manual"
                            }))
                            await asyncio.sleep(0.3)
                            try:
                                import subprocess, tempfile, os
                                # edge-tts输出mp3，再用ffmpeg转为24kHz单声道16bit wav
                                mp3_path = tempfile.mktemp(suffix='.mp3')
                                wav_path = tempfile.mktemp(suffix='.wav')
                                proc = await asyncio.create_subprocess_exec(
                                    'edge-tts', '--voice', 'zh-CN-XiaoxiaoNeural',
                                    '--text', text_content, '--write-media', mp3_path,
                                    stdout=asyncio.subprocess.PIPE,
                                    stderr=asyncio.subprocess.PIPE
                                )
                                await proc.communicate()
                                if proc.returncode != 0:
                                    raise Exception("edge-tts failed")
                                # ffmpeg转码：mp3 -> 16kHz mono 16bit wav（直接输出xiaozhi服务端需要的采样率）
                                ffmpeg_proc = await asyncio.create_subprocess_exec(
                                    'ffmpeg', '-y', '-i', mp3_path,
                                    '-ar', '16000', '-ac', '1', '-sample_fmt', 's16',
                                    wav_path,
                                    stdout=asyncio.subprocess.PIPE,
                                    stderr=asyncio.subprocess.PIPE
                                )
                                await ffmpeg_proc.communicate()
                                os.remove(mp3_path)
                                if ffmpeg_proc.returncode != 0 or not os.path.exists(wav_path):
                                    raise Exception("ffmpeg failed")
                                # 直接用opus编码16kHz音频发送WebSocket二进制帧，绕过send_audio
                                import wave, opuslib
                                encoder = opuslib.Encoder(fs=16000, channels=1, application=opuslib.APPLICATION_VOIP)
                                frame_size = 16000 * 60 // 1000  # 60ms = 960 samples
                                with wave.open(wav_path, 'rb') as wf:
                                    while True:
                                        pcm_data = wf.readframes(frame_size)
                                        if not pcm_data:
                                            break
                                        if len(pcm_data) < frame_size * 2:
                                            pcm_data = pcm_data + b'\x00' * (frame_size * 2 - len(pcm_data))
                                        opus_data = encoder.encode(pcm_data, frame_size)
                                        await xiaozhi.server.websocket.send(opus_data)
                                os.remove(wav_path)
                                logger.info("长文本TTS音频发送完成 [%s]", pc.mac_address)
                            except Exception as tts_err:
                                logger.warning("TTS失败，兜底发送短唤醒词: %s", tts_err)
                                await xiaozhi.server.send_wake_word(text_content[:10])
                            await asyncio.sleep(0.1)
                            await xiaozhi.server.send_silence_audio(1.5)
                            await xiaozhi.server.websocket.send(_json.dumps({
                                "session_id": xiaozhi.server.session_id,
                                "type": "listen", "state": "stop"
                            }))
                            logger.info("长文本流程完成 [%s]", pc.mac_address)
                    except Exception as e:
                        logger.error("文字输入处理失败: %s", e)
                return

            if xiaozhi.server.output_audio_queue:
                return

            send_text_dict = {
                "doublehit": {
                    "Head": "拍了拍你的头",
                    "Face": "拍了拍你的脸",
                    "Body": "拍了拍你的身体",
                },
                "swipe": {
                    "Head": "摸了摸你的头",
                    "Face": "摸了摸你的脸",
                },
            }
            send_text = send_text_dict.get(message.get("event", ""), {}).get(message.get("area", ""), "")
            if send_text:
                await xiaozhi.server.send_wake_word(send_text)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info("Connection state is %s %s %s", pc.connectionState, pc.mac_address, pc.client_ip)
        if pc.connectionState == "connected":
            await xiaozhi.start()

        if pc.connectionState in ["failed", "closed", "disconnected"]:
            # 取消视频消费任务
            if hasattr(pc, "video_task") and not pc.video_task.done():
                pc.video_task.cancel()
                try:
                    await pc.video_task
                except asyncio.CancelledError:
                    pass
            # Stop all AudioFaceSwapper instances
            if xiaozhi.server:
                await xiaozhi.server.close()
            await pc.close()
            pcs.discard(pc)

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            t = AudioFaceSwapper(xiaozhi, track)
            pc.addTrack(t)
            # 将 track 实例存储在 pc 对象上
            pc.audio_track = t
        elif track.kind == "video":
            # 不 addTrack 视频轨道，只消费视频帧（节省 CPU）
            async def consume_video():
                while True:
                    try:
                        frame = await track.recv()
                        if xiaozhi and xiaozhi.server:
                            xiaozhi.server.video_frame = frame
                    except asyncio.CancelledError:
                        logger.debug("视频消费任务被取消 [%s %s]", pc.mac_address, pc.client_ip)
                        break
                    except Exception as e:
                        logger.debug("视频消费任务异常退出 [%s %s]: %s", pc.mac_address, pc.client_ip, e)
                        break
            # 保存任务引用以便后续取消
            pc.video_task = asyncio.create_task(consume_video())

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)


async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


def run():
    app = web.Application()
    app.on_shutdown.append(on_shutdown)

    app.router.add_get("/", index)
    # app.router.add_get("/chat", chat)
    app.router.add_get("/chatv2", chatv2)

    app.router.add_get("/api/ice", ice)
    app.router.add_post("/api/offer", offer)
    app.router.add_static("/static/", path=os.path.join(ROOT, "static"), name="static")
    app.router.add_static("/image/", path=os.path.join(ROOT, "image"), name="image")
    app.router.add_static("/locales/", path=os.path.join(ROOT, "locales"), name="locales")

    web.run_app(app, host="0.0.0.0", port=PORT)
