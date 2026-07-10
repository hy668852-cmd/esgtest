"""
回声消除管理器
Echo Cancellation Manager - 统一管理回声消除逻辑
"""

import numpy as np

from src.audio.echo_canceller import EchoCanceller


class EchoCancellationManager:
    """
    回声消除管理器
    负责统一管理回声消除的所有逻辑，包括：
    - 回声消除器的初始化和配置
    - 音频处理和安全检查
    - 调试信息输出
    - 自适应参数调整
    """

    def __init__(self, enable_echo_cancellation=True, enable_debug=False):
        """
        初始化回声消除管理器

        Args:
            enable_echo_cancellation: 是否启用回声消除
            enable_debug: 是否启用调试信息
        """
        self.enable_echo_cancellation = enable_echo_cancellation
        self.enable_debug = enable_debug

        # 初始化回声消除器
        self.echo_canceller = EchoCanceller()

        # 参考信号存储
        self.reference_audio = None

        # 统计信息
        self.frame_count = 0
        self.over_suppression_count = 0

        # 安全检查参数
        self.min_energy_ratio = 0.1  # 最小能量比例，防止过度抑制
        self.min_original_rms = 100  # 最小原始RMS阈值
        self.mix_ratio = 0.3  # 过度抑制时的原始音频混合比例

        # 调试参数
        self.debug_interval = 200  # 调试信息输出间隔（帧数）

    def update_reference_audio(self, reference_samples):
        """
        更新参考音频信号

        Args:
            reference_samples: 参考音频样本 (numpy array)
        """
        if reference_samples is None:
            return

        try:
            # 验证参考音频的有效性
            if len(reference_samples) == 0:
                # self._log_debug("参考音频为空，跳过更新")
                return

            # 检查数值有效性
            if not np.all(np.isfinite(reference_samples)):
                # self._log_debug("参考音频包含无效值，进行清理")
                reference_samples = np.where(np.isfinite(reference_samples), reference_samples, 0)

            self.reference_audio = reference_samples.copy()
            # 同时添加到回声消除器的缓冲区
            self.echo_canceller.add_reference_audio(reference_samples)

        except Exception as e:
            self._log_debug(f"更新参考音频失败: {e}")
            # 更新失败时不影响现有的参考音频

    def process_microphone_audio(self, input_audio):
        """
        处理麦克风输入的音频

        Args:
            input_audio: 麦克风输入的音频数据 (numpy array, int16)

        Returns:
            numpy array: 处理后的音频数据 (int16)
        """
        self.frame_count += 1

        # 输入验证
        if input_audio is None or len(input_audio) == 0:
            self._log_debug(f"Frame {self.frame_count}: 输入音频为空")
            return np.zeros(960, dtype=np.int16)  # 返回静音帧

        # 检查输入音频的数值有效性
        if not np.all(np.isfinite(input_audio)):
            self._log_debug(f"Frame {self.frame_count}: 输入音频包含无效值，使用零填充")
            input_audio = np.where(np.isfinite(input_audio), input_audio, 0)

        # 如果回声消除未启用或没有参考信号，直接返回原始音频
        if not self.enable_echo_cancellation or self.reference_audio is None:
            # self._log_debug(f"Frame {self.frame_count}: 回声消除未启用或无参考信号")
            return input_audio

        # 执行回声消除 - 添加异常处理
        try:
            cleaned_audio = self.echo_canceller.process_audio(input_audio, reference_audio=self.reference_audio)
        except Exception as e:
            self._log_debug(f"Frame {self.frame_count}: 回声消除处理失败: {e}")
            # 回声消除失败时，返回原始音频
            return input_audio

        # 安全检查和后处理
        try:
            final_audio = self._safety_check_and_mix(input_audio, cleaned_audio)
        except Exception as e:
            self._log_debug(f"Frame {self.frame_count}: 安全检查失败: {e}")
            # 安全检查失败时，返回清理后的音频或原始音频
            final_audio = cleaned_audio if cleaned_audio is not None else input_audio

        # 输出调试信息
        self._output_debug_info(input_audio, cleaned_audio, final_audio)

        return final_audio

    def _safety_check_and_mix(self, original_audio, cleaned_audio):
        """
        安全检查和音频混合

        Args:
            original_audio: 原始音频
            cleaned_audio: 清理后的音频

        Returns:
            numpy array: 最终处理后的音频
        """
        # 计算音频能量 - 使用安全的数值计算
        original_float64 = original_audio.astype(np.float64)
        cleaned_float64 = cleaned_audio.astype(np.float64)

        original_rms = np.sqrt(np.mean(original_float64**2))
        cleaned_rms = np.sqrt(np.mean(cleaned_float64**2))

        # 检查RMS值的有效性
        if not np.isfinite(original_rms):
            original_rms = 0.0
        if not np.isfinite(cleaned_rms):
            cleaned_rms = 0.0

        # 检查是否过度抑制
        if cleaned_rms < original_rms * self.min_energy_ratio and original_rms > self.min_original_rms:

            # 过度抑制，混合原始音频
            self.over_suppression_count += 1
            mixed_audio = self._mix_audio(original_audio, cleaned_audio, self.mix_ratio)

            if self.frame_count % 100 == 0:
                self._log_debug(
                    f"Frame {self.frame_count}: 检测到过度抑制，混合原始音频 "
                    f"(总计: {self.over_suppression_count}次)"
                )

            return mixed_audio

        return cleaned_audio

    def _mix_audio(self, original_audio, processed_audio, original_ratio):
        """
        混合原始音频和处理后的音频

        Args:
            original_audio: 原始音频
            processed_audio: 处理后的音频
            original_ratio: 原始音频的混合比例

        Returns:
            numpy array: 混合后的音频
        """
        processed_ratio = 1.0 - original_ratio
        mixed_audio = (
            original_audio.astype(np.float32) * original_ratio + processed_audio.astype(np.float32) * processed_ratio
        )
        return mixed_audio.astype(np.int16)

    def _output_debug_info(self, original_audio, cleaned_audio, final_audio):
        """
        输出调试信息

        Args:
            original_audio: 原始音频
            cleaned_audio: 清理后的音频
            final_audio: 最终音频
        """
        if not self.enable_debug or self.frame_count % self.debug_interval != 0:
            return

        original_rms = np.sqrt(np.mean(original_audio.astype(np.float32) ** 2))
        cleaned_rms = np.sqrt(np.mean(cleaned_audio.astype(np.float32) ** 2))
        final_rms = np.sqrt(np.mean(final_audio.astype(np.float32) ** 2))

        ratio = cleaned_rms / original_rms if original_rms > 0 else 0

        # 获取回声消除器统计信息
        echo_stats = self.echo_canceller.get_statistics()

        self._log_debug(
            f"Frame {self.frame_count}: "
            f"Original RMS={original_rms:.2f}, "
            f"Cleaned RMS={cleaned_rms:.2f}, "
            f"Final RMS={final_rms:.2f}, "
            f"Ratio={ratio:.3f}, "
            f"Echo Detection Rate={echo_stats['echo_detection_rate']:.3f}, "
            f"Over Suppression Count={self.over_suppression_count}"
        )

    def _log_debug(self, message):
        """输出调试信息"""
        pass
        # if self.enable_debug:
        #     print(f"[EchoCancellationManager] {message}")

    def get_statistics(self):
        """
        获取管理器统计信息

        Returns:
            dict: 统计信息
        """
        echo_stats = self.echo_canceller.get_statistics()

        return {
            "manager_stats": {
                "total_frames": self.frame_count,
                "over_suppression_count": self.over_suppression_count,
                "over_suppression_rate": self.over_suppression_count / max(1, self.frame_count),
                "echo_cancellation_enabled": self.enable_echo_cancellation,
                "has_reference_audio": self.reference_audio is not None,
            },
            "echo_canceller_stats": echo_stats,
        }

    def reset(self):
        """重置管理器状态"""
        self.echo_canceller.reset()
        self.reference_audio = None
        self.frame_count = 0
        self.over_suppression_count = 0

    def set_parameters(self, **kwargs):
        """
        动态设置参数

        Args:
            **kwargs: 参数字典，可包含：
                - enable_echo_cancellation: 是否启用回声消除
                - min_energy_ratio: 最小能量比例
                - mix_ratio: 混合比例
                - debug_interval: 调试输出间隔
        """
        if "enable_echo_cancellation" in kwargs:
            self.enable_echo_cancellation = kwargs["enable_echo_cancellation"]
            self._log_debug(f"回声消除已{'启用' if self.enable_echo_cancellation else '禁用'}")

        if "min_energy_ratio" in kwargs:
            self.min_energy_ratio = kwargs["min_energy_ratio"]
            self._log_debug(f"最小能量比例设置为: {self.min_energy_ratio}")

        if "mix_ratio" in kwargs:
            self.mix_ratio = kwargs["mix_ratio"]
            self._log_debug(f"混合比例设置为: {self.mix_ratio}")

        if "debug_interval" in kwargs:
            self.debug_interval = kwargs["debug_interval"]
            self._log_debug(f"调试输出间隔设置为: {self.debug_interval}")
