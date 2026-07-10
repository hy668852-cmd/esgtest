"""
回声消除管理器使用示例
Echo Cancellation Manager Usage Examples
"""

# 示例1: 基本使用
from src.audio.echo_manager import EchoCancellationManager

# 创建管理器
echo_manager = EchoCancellationManager(enable_echo_cancellation=True, enable_debug=True)


# 处理音频的典型流程
def process_audio_example(microphone_audio, speaker_audio):
    """
    音频处理示例

    Args:
        microphone_audio: 麦克风输入的音频数据
        speaker_audio: 扬声器输出的音频数据
    """
    # 1. 更新参考音频（扬声器输出）
    echo_manager.update_reference_audio(speaker_audio)

    # 2. 处理麦克风音频（消除回声）
    cleaned_audio = echo_manager.process_microphone_audio(microphone_audio)

    return cleaned_audio


# 示例2: 动态配置
def configure_echo_cancellation_example():
    """配置回声消除参数的示例"""

    # 创建管理器
    manager = EchoCancellationManager()

    # 动态调整参数
    manager.set_parameters(
        enable_echo_cancellation=True,
        min_energy_ratio=0.15,  # 调整最小能量比例
        mix_ratio=0.25,  # 调整混合比例
        debug_interval=100,  # 调整调试输出频率
    )

    # 获取统计信息
    stats = manager.get_statistics()
    print(f"处理帧数: {stats['manager_stats']['total_frames']}")
    print(f"过度抑制率: {stats['manager_stats']['over_suppression_rate']:.3f}")

    return manager


# 示例3: 在AudioFaceSwapper中的使用
def audio_face_swapper_example():
    """AudioFaceSwapper中的使用示例"""

    # 假设有一个AudioFaceSwapper实例
    # audio_swapper = AudioFaceSwapper(xiaozhi, track)

    # 获取回声消除统计信息
    # stats = audio_swapper.get_echo_cancellation_stats()
    # print(f"回声检测率: {stats['echo_canceller_stats']['echo_detection_rate']:.3f}")

    # 临时禁用回声消除
    # audio_swapper.set_echo_cancellation_enabled(False)

    # 调整回声消除参数
    # audio_swapper.configure_echo_cancellation(
    #     min_energy_ratio=0.2,
    #     mix_ratio=0.4
    # )

    # 重置回声消除状态
    # audio_swapper.reset_echo_cancellation()

    pass


# 示例4: 高级配置场景
def advanced_configuration_example():
    """高级配置场景示例"""

    # 为不同场景创建不同配置的管理器

    # 安静环境配置 - 更激进的回声消除
    quiet_environment = EchoCancellationManager(enable_echo_cancellation=True, enable_debug=False)
    quiet_environment.set_parameters(min_energy_ratio=0.05, mix_ratio=0.2)  # 更低的阈值  # 更少的原始音频混合

    # 嘈杂环境配置 - 更保守的回声消除
    noisy_environment = EchoCancellationManager(enable_echo_cancellation=True, enable_debug=True)
    noisy_environment.set_parameters(min_energy_ratio=0.3, mix_ratio=0.5)  # 更高的阈值  # 更多的原始音频混合

    # 调试模式配置 - 详细的日志输出
    debug_mode = EchoCancellationManager(enable_echo_cancellation=True, enable_debug=True)
    debug_mode.set_parameters(debug_interval=50)  # 更频繁的调试输出

    return {"quiet": quiet_environment, "noisy": noisy_environment, "debug": debug_mode}


if __name__ == "__main__":
    print("回声消除管理器使用示例")
    print("=" * 50)

    # 运行配置示例
    manager = configure_echo_cancellation_example()
    print(f"管理器创建成功: {manager}")

    # 运行高级配置示例
    configs = advanced_configuration_example()
    print(f"创建了 {len(configs)} 种配置")

    print("示例运行完成!")
