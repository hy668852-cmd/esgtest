# 回声消除配置文件
# Echo Cancellation Configuration


class EchoConfig:
    """回声消除配置类"""

    # 自适应滤波器参数 - 更保守的设置以避免过度抑制
    ADAPTIVE_FILTER_LENGTH = 1024  # 恢复到较小的滤波器长度
    LEARNING_RATE = 0.02  # 降低学习率以避免过度调整

    # 缓冲区参数 - 适中的缓冲区大小
    ECHO_BUFFER_SIZE = 100  # 回声缓冲区大小 (约2秒)
    INPUT_BUFFER_SIZE = 50  # 输入缓冲区大小

    # 预热参数 - 更温和的预热处理
    WARMUP_DURATION = 2.0  # 增加预热时间，让算法稳定
    WARMUP_GAIN_FACTOR = 0.7  # 提高预热期间的增益因子，保留更多原始音频

    # 噪声门限参数 - 更保守的门限设置
    NOISE_GATE_THRESHOLD = 200  # 更低的门限，但配合更温和的衰减
    NOISE_GATE_ATTENUATION = 0.3  # 减少衰减，保留更多音频信号

    # 音频处理参数
    GAIN_FACTOR = 1.0  # 正常增益因子
    SAMPLE_RATE = 48000  # 采样率

    # 客户端音频约束参数 - 优化以增强回声消除效果
    CLIENT_AUDIO_CONSTRAINTS = {
        "echoCancellation": True,
        "echoCancellationType": "system",  # 使用系统级回声消除
        "noiseSuppression": True,
        "autoGainControl": True,
        "googEchoCancellation": True,
        "googAutoGainControl": True,
        "googNoiseSuppression": True,
        "googHighpassFilter": True,
        "googTypingNoiseDetection": True,
        "googAudioMirroring": False,
        "googEchoCancellation2": True,  # 启用增强的回声消除
        "googDAEchoCancellation": True,  # 启用数字音频回声消除
        "googNoiseReduction": True,  # 额外的噪声抑制
        "latency": 0.02,  # 增加到20ms延迟以改善回声消除效果
        "sampleRate": 48000,
        "sampleSize": 16,
        "channelCount": 1,
    }

    @classmethod
    def get_adaptive_params(cls):
        """获取自适应滤波器参数"""
        return {"filter_length": cls.ADAPTIVE_FILTER_LENGTH, "learning_rate": cls.LEARNING_RATE}

    @classmethod
    def get_buffer_params(cls):
        """获取缓冲区参数"""
        return {"echo_buffer_size": cls.ECHO_BUFFER_SIZE, "input_buffer_size": cls.INPUT_BUFFER_SIZE}

    @classmethod
    def get_warmup_params(cls):
        """获取预热参数"""
        return {"duration": cls.WARMUP_DURATION, "gain_factor": cls.WARMUP_GAIN_FACTOR}

    @classmethod
    def get_noise_gate_params(cls):
        """获取噪声门限参数"""
        return {"threshold": cls.NOISE_GATE_THRESHOLD, "attenuation": cls.NOISE_GATE_ATTENUATION}
