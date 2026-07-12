from fractions import Fraction

import av
import numpy as np
from aiortc import AudioStreamTrack

from src.audio.echo_manager import EchoCancellationManager


class AudioFaceSwapper(AudioStreamTrack):
    kind = "audio"

    def __init__(self, xiaozhi, track):
        super().__init__()
        self.track = track
        self.sample_rate = 48000
        self.xiaozhi = xiaozhi

        # 初始化回声消除管理器（禁用服务端回声消除，浏览器端已有足够的回声消除能力）
        self.echo_manager = EchoCancellationManager(enable_echo_cancellation=False, enable_debug=False)

        # 预分配静音帧，避免每帧重复创建
        self._silence_samples = np.zeros(960, dtype=np.int16)

    def empty_frame(self):
        new_frame = av.AudioFrame.from_ndarray(
            self._silence_samples.reshape(1, -1), format="s16", layout="mono"
        )
        new_frame.sample_rate = self.sample_rate
        new_frame.pts = 0
        return new_frame

    async def recv(self):
        original_frame = await self.track.recv()

        if not self.xiaozhi.server:
            return self.empty_frame()

        pcm_data = np.frombuffer(original_frame.planes[0], dtype=np.int16)

        # 使用回声消除管理器处理麦克风音频
        cleaned_pcm_data = self.echo_manager.process_microphone_audio(pcm_data)

        # 发送处理后的音频到服务端
        await self.xiaozhi.server.send_audio(cleaned_pcm_data.tobytes())

        if not self.xiaozhi.server:
            return self.empty_frame()

        # 直接从SDK queue取一帧播放，不做额外缓冲
        samples = None
        if self.xiaozhi.server.output_audio_queue:
            try:
                samples = self.xiaozhi.server.output_audio_queue.popleft()
            except (IndexError, Exception):
                pass

        if samples is not None:
            self.echo_manager.update_reference_audio(samples)
            new_frame = av.AudioFrame.from_ndarray(
                samples.reshape(1, -1), format="s16", layout="mono"
            )
            new_frame.sample_rate = self.sample_rate
            new_frame.pts = original_frame.pts
            new_frame.time_base = Fraction(1, self.sample_rate)
            return new_frame

        return self.empty_frame()

    def get_echo_cancellation_stats(self):
        """获取回声消除统计信息"""
        return self.echo_manager.get_statistics()

    def set_echo_cancellation_enabled(self, enabled):
        """启用/禁用回声消除"""
        self.echo_manager.set_parameters(enable_echo_cancellation=enabled)

    def configure_echo_cancellation(self, **kwargs):
        """配置回声消除参数"""
        self.echo_manager.set_parameters(**kwargs)

    def reset_echo_cancellation(self):
        """重置回声消除状态"""
        self.echo_manager.reset()
