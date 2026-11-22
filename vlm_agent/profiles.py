"""Model / framework profiles. Switching a profile changes the resident model, the modes it uses, the prompts and the board trigger mode."""
PROFILES = {
    "qwen3vl_rgb": dict(
        label="Qwen3-VL-2B · RGB only (video trigger)",
        model_name="Qwen3-VL-2B Q4_K_M", hf_repo="Qwen/Qwen3-VL-2B-Instruct-GGUF", manifest_key=None,
        mode="rgb", llama_args=[], window_s=4.0, max_frames=4, long_edge=336, asr=False,
        board=dict(trig_mode=0, max_chunk_s=2),                 # video detector only
    ),
    "lfm3_omni_av": dict(
        label="LFM3-Omni-2B · RGB + audio (video OR audio trigger)",
        model_name="LFM3-Omni-2B Q4_K_M", hf_repo="LiquidAI/LFM3-Omni-2B-GGUF", manifest_key="lfm3_omni",
        mode="rgb_audio", llama_args=["--reasoning", "off"], window_s=4.0, max_frames=8, long_edge=336, asr=True,
        board=dict(trig_mode=1, max_chunk_s=2),                 # union of video and audio change
    ),
}
DEFAULT = "qwen3vl_rgb"
ASR_GATE_RMS = 150        # int16 RMS the audio slice must exceed before the speech pass runs
SILENT_RMS = 30           # below this the slice is described as near-silent
SPEECH_CV = 0.45          # std/mean of the loud 20 ms frame levels a clip needs before speech recognition is attempted (tones/steady noise are below)
