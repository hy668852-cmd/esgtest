from fractions import Fraction

import collections

import av
import numpy as np
from aiortc import AudioStreamTrack

from src.audio.echo_manager import EchoCancellationManager

resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)


class AudioFaceSwapper(AudioStreamTrack):
    kind = "audio"

    def __init__(self, xiaozhi, track):
        super().__init__()
        self.track = track
        self.sample_rate = 48000
        self.xiaozhi = xiaozhi

        # 初始化回声消除管理器（禁用服务端回声消除，浏览器端已有足够的回声消除能力）
        self.echo_manager = EchoCancellationManager(enable_echo_cancellation=False, enable_debug=False)

        # Playback buffer：使用deque，O(1) 的 popleft 操作，maxlen 防止内存溢出
        self._playback_buffer = collections.deque(maxlen=200)
        self._min_buffer_frames = 20   # 预缓冲20帧 = 约400ms，能吸收更大的TTS延迟抖动
        self._playback_started = False
        self._silence_samples = np.zeros(960, dtype=np.int16)  # 预生成静音帧，避免每次重复创建
        self._empty_cycles = 0         # buffer连续为空的周期计数
        self._max_empty_cycles = 25    # 25 * 20ms = 500ms，超过则认为本轮TTS结束，下一轮重新预缓冲

    def _create_frame(self, samples, pts, time_base):
        """创建音频帧"""
        frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1),
            format="s16",
            layout="mono",
        )
        frame.sample_rate = self.sample_rate
        frame.pts = pts
        frame.time_base = time_base
        return frame

    def _get_silence_frame(self, pts, time_base):
        """返回静音帧"""
        return self._create_frame(self._silence_samples, pts, time_base)

    def _fill_buffer(self):
        """将SDK queue中的所有帧拉取到playback buffer"""
        if not self.xiaozhi.server:
            return
        while self.xiaozhi.server.output_audio_queue:
            try:
                self._playback_buffer.append(self.xiaozhi.server.output_audio_queue.popleft())
            except (IndexError, Exception):
                break

    def _pop_frame(self):
        """从buffer取一帧，如果buffer空返回None"""
        if self._playback_buffer:
            return self._playback_buffer.popleft()
        return None

    async def recv(self):
        # 接收原始音频帧
        original_frame = await self.track.recv()

        if not self.xiaozhi.server:
            return self._get_silence_frame(original_frame.pts, original_frame.time_base)

        pcm_data = np.frombuffer(original_frame.planes[0], dtype=np.int16)

        # 使用回声消除管理器处理麦克风音频
        cleaned_pcm_data = self.echo_manager.process_microphone_audio(pcm_data)

        # 发送处理后的音频到服务端
        await self.xiaozhi.server.send_audio(cleaned_pcm_data.tobytes())

        if not self.xiaozhi.server:
            return self._get_silence_frame(original_frame.pts, original_frame.time_base)

        # 从SDK queue拉取所有可用帧到playback buffer
        self._fill_buffer()

        # 预缓冲阶段：尚未积累足够帧，返回静音
        if not self._playback_started:
            if len(self._playback_buffer) >= self._min_buffer_frames:
                self._playback_started = True
            else:
                return self._get_silence_frame(original_frame.pts, original_frame.time_base)

        # 从buffer取一帧播放
        samples = self._pop_frame()
        if samples is not None:
            self._empty_cycles = 0
            # 更新回声消除管理器的参考音频
            self.echo_manager.update_reference_audio(samples)
            return self._create_frame(samples, original_frame.pts, original_frame.time_base)

        # buffer空了：播放静音（不再重复上一帧，避免噪音）
        self._empty_cycles += 1
        if self._empty_cycles > self._max_empty_cycles:
            # 连续空了超过500ms，认为本轮TTS结束，下一轮重新预缓冲
            self._playback_started = False
            self._empty_cycles = 0

        return self._get_silence_frame(original_frame.pts, original_frame.time_base)

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
