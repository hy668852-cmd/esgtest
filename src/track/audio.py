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

        # 预缓冲：TTS开始前先积累足够帧再播放，消除sentence间卡顿
        self._buffer = collections.deque(maxlen=500)
        self._pre_buffer_count = 30    # 预缓冲30帧 ≈ 600ms，吸收LLM生成速度不均匀
        self._playing = False           # 是否正在播放TTS音频
        self._tts_active = False        # TTS会话是否活跃（queue有数据）
        self._silence_cycles = 0        # 连续静音周期计数，用于检测TTS结束

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
        cleaned_pcm_data = self.echo_manager.process_microphone_audio(pcm_data)
        await self.xiaozhi.server.send_audio(cleaned_pcm_data.tobytes())

        if not self.xiaozhi.server:
            return self.empty_frame()

        # 1. 将SDK queue中所有可用帧拉入buffer
        has_new_data = False
        if self.xiaozhi.server.output_audio_queue:
            while self.xiaozhi.server.output_audio_queue:
                try:
                    self._buffer.append(self.xiaozhi.server.output_audio_queue.popleft())
                    has_new_data = True
                except (IndexError, Exception):
                    break

        # 2. 状态检测
        if has_new_data:
            self._silence_cycles = 0
            if not self._tts_active:
                # 新一轮TTS开始
                self._tts_active = True
                self._playing = False
                self._buffer.clear()
                # 重新拉取（刚清空了）
                if self.xiaozhi.server.output_audio_queue:
                    while self.xiaozhi.server.output_audio_queue:
                        try:
                            self._buffer.append(self.xiaozhi.server.output_audio_queue.popleft())
                        except (IndexError, Exception):
                            break
        else:
            self._silence_cycles += 1
            # 连续空了约1秒（50 * 20ms），认为TTS结束
            if self._tts_active and self._silence_cycles > 50:
                self._tts_active = False
                self._playing = False
                self._buffer.clear()

        # 3. 预缓冲阶段：TTS已开始但帧数不够，返回静音等待
        if self._tts_active and not self._playing:
            if len(self._buffer) >= self._pre_buffer_count:
                self._playing = True  # 积累够了，开始播放
            else:
                return self.empty_frame()

        # 4. 播放阶段：从buffer取一帧
        if self._playing and self._buffer:
            samples = self._buffer.popleft()
            self.echo_manager.update_reference_audio(samples)
            new_frame = av.AudioFrame.from_ndarray(
                samples.reshape(1, -1), format="s16", layout="mono"
            )
            new_frame.sample_rate = self.sample_rate
            new_frame.pts = original_frame.pts
            new_frame.time_base = Fraction(1, self.sample_rate)
            return new_frame

        # 5. buffer空了且TTS还在（sentence间隙），返回静音但保持playing状态
        #    不重置playing，这样下一批帧到来时直接播放，不需要重新预缓冲
        return self.empty_frame()

    def get_echo_cancellation_stats(self):
        return self.echo_manager.get_statistics()

    def set_echo_cancellation_enabled(self, enabled):
        self.echo_manager.set_parameters(enable_echo_cancellation=enabled)

    def configure_echo_cancellation(self, **kwargs):
        self.echo_manager.set_parameters(**kwargs)

    def reset_echo_cancellation(self):
        self.echo_manager.reset()
