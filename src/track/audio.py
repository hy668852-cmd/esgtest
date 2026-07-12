from fractions import Fraction

import collections

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

        # 预分配静音帧
        self._silence_samples = np.zeros(960, dtype=np.int16)

        # 播放缓冲：用deque，maxlen防止内存溢出
        self._playback_buffer = collections.deque(maxlen=200)
        self._started = False           # TTS是否已开始播放
        self._empty_count = 0           # 连续空帧计数，用于检测TTS结束
        self._audio_pts = 0             # 独立的音频pts，确保时间戳连续递增

    def _get_silence(self):
        """返回静音帧，pts自增"""
        frame = av.AudioFrame.from_ndarray(
            self._silence_samples.reshape(1, -1), format="s16", layout="mono"
        )
        frame.sample_rate = self.sample_rate
        frame.pts = self._audio_pts
        frame.time_base = Fraction(1, self.sample_rate)
        self._audio_pts += 960
        return frame

    def _get_frame(self, samples):
        """返回音频帧，pts根据样本数自增"""
        frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1), format="s16", layout="mono"
        )
        frame.sample_rate = self.sample_rate
        frame.pts = self._audio_pts
        frame.time_base = Fraction(1, self.sample_rate)
        self._audio_pts += len(samples)
        return frame

    async def recv(self):
        original = await self.track.recv()

        if not self.xiaozhi.server:
            return self._get_silence()

        # 麦克风音频 → 回声消除 → 发送服务端
        pcm_data = np.frombuffer(original.planes[0], dtype=np.int16)
        cleaned_pcm_data = self.echo_manager.process_microphone_audio(pcm_data)
        await self.xiaozhi.server.send_audio(cleaned_pcm_data.tobytes())

        if not self.xiaozhi.server:
            return self._get_silence()

        # 将SDK queue中所有可用帧拉入播放缓冲
        while self.xiaozhi.server.output_audio_queue:
            try:
                self._playback_buffer.append(self.xiaozhi.server.output_audio_queue.popleft())
            except (IndexError, Exception):
                break

        # 播放缓冲中有帧
        if self._playback_buffer:
            self._empty_count = 0

            # 预缓冲：只在TTS开始播放前等待5帧（100ms）
            if not self._started:
                if len(self._playback_buffer) >= 5:
                    self._started = True
                else:
                    return self._get_silence()

            # 正常播放
            samples = self._playback_buffer.popleft()
            self.echo_manager.update_reference_audio(samples)
            return self._get_frame(samples)

        # 播放缓冲空了
        self._empty_count += 1
        # 连续空了超过1秒（50 * 20ms），认为本轮TTS结束，下次重新预缓冲
        if self._empty_count > 50:
            self._started = False
            self._empty_count = 0

        return self._get_silence()

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
