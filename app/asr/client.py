import logging
import os
from pathlib import Path

import httpx

from app.core.config import Config

logger = logging.getLogger("wsnote.asr")

# 支持的音频格式
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# ──────────────────────────────────────────────
# 1. 本地 faster-whisper（优先）
# ──────────────────────────────────────────────

class FasterWhisperASR:
    """使用本地 faster-whisper 模型进行语音转写。"""

    def __init__(self, model, beam_size: int = 5):
        self.model = model
        self.beam_size = beam_size

    def available(self) -> bool:
        return self.model is not None

    def transcribe(self, audio_bytes: bytes, filename: str) -> str:
        # faster-whisper 接受文件路径或文件对象，这里用临时文件
        import tempfile, os
        suffix = Path(filename).suffix or ".mp3"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            segments, _ = self.model.transcribe(tmp_path, beam_size=self.beam_size)
            return "".join(seg.text for seg in segments).strip()
        finally:
            os.unlink(tmp_path)


_FW_MODEL_NAMES = [
    "Systran/faster-whisper-large-v3",
    "Systran/faster-whisper-large-v2",
    "Systran/faster-whisper-medium",
    "Systran/faster-whisper-small",
    "Systran/faster-whisper-base",
    "Systran/faster-whisper-tiny",
]


def _find_cached_model(cache_dir: Path) -> str | None:
    """扫描目录，返回已下载的最优 faster-whisper 模型路径。
    支持两种布局：
    1. HF 缓存结构：models--Systran--faster-whisper-small/snapshots/<hash>/
    2. 扁平目录：faster-whisper-small/model.bin
    """
    if not cache_dir.is_dir():
        return None
    for name in _FW_MODEL_NAMES:
        short = name.split("/")[-1]  # e.g. faster-whisper-small
        # 扁平目录（直接含 model.bin）
        flat = cache_dir / short
        if flat.is_dir() and (flat / "model.bin").is_file():
            return str(flat)
        # HF 缓存结构
        safe = name.replace("/", "--")
        hf = cache_dir / f"models--{safe}"
        if hf.is_dir():
            snapshots = hf / "snapshots"
            if snapshots.is_dir():
                for snap in snapshots.iterdir():
                    if snap.is_dir() and (snap / "model.bin").is_file():
                        return str(snap)
    return None


def _try_faster_whisper(model_path: str | None, device: str, compute_type: str):
    """尝试加载 faster-whisper，成功返回 FasterWhisperASR，失败返回 None。"""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.debug("faster-whisper 未安装，跳过")
        return None

    # 用户手动指定路径
    if model_path and os.path.exists(model_path):
        resolved = model_path
    else:
        # 项目本地 models/
        project_root = Path(__file__).resolve().parent.parent.parent
        local = _find_cached_model(project_root / "models")
        if local:
            resolved = local
        else:
            # WorkBuddy 本地模型目录（手动修复过的 HF 缓存）
            wb_models = Path.home() / ".workbuddy" / "binaries" / "models"
            wb = _find_cached_model(wb_models)
            if wb:
                resolved = wb
            else:
                # HuggingFace 缓存
                cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
                cached = _find_cached_model(cache_dir)
                resolved = cached or _FW_MODEL_NAMES[3]

    try:
        logger.info("加载 faster-whisper 模型: %s (device=%s)", resolved, device)
        model = WhisperModel(resolved, device=device, compute_type=compute_type)
        logger.info("faster-whisper 加载成功")
        return FasterWhisperASR(model)
    except Exception as e:
        logger.warning("faster-whisper 加载失败: %s", e)
        return None


# ──────────────────────────────────────────────
# 2. 本地 openai-whisper（次选）
# ──────────────────────────────────────────────

class OpenAIWhisperASR:
    """使用本地 openai-whisper 模型进行语音转写。"""

    def __init__(self, model):
        self.model = model

    def available(self) -> bool:
        return self.model is not None

    def transcribe(self, audio_bytes: bytes, filename: str) -> str:
        import tempfile, os
        suffix = Path(filename).suffix or ".mp3"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            result = self.model.transcribe(tmp_path)
            return result.get("text", "").strip()
        finally:
            os.unlink(tmp_path)


def _try_openai_whisper(model_path: str | None):
    """尝试加载 openai-whisper，成功返回 OpenAIWhisperASR，失败返回 None。"""
    try:
        import whisper
    except ImportError:
        logger.debug("openai-whisper 未安装，跳过")
        return None

    # openai-whisper 模型名：tiny/base/small/medium/large
    model_name = model_path if model_path and not os.path.isdir(model_path) else "medium"
    # 如果是目录则尝试自动检测
    if model_path and os.path.isdir(model_path):
        for name in ["large-v3", "large-v2", "large", "medium", "small", "base", "tiny"]:
            if (Path(model_path) / f"{name}.pt").exists():
                model_name = name
                break
        else:
            model_name = "medium"

    try:
        logger.info("加载 openai-whisper 模型: %s", model_name)
        model = whisper.load_model(model_name, download_root=model_path)
        logger.info("openai-whisper 加载成功")
        return OpenAIWhisperASR(model)
    except Exception as e:
        logger.warning("openai-whisper 加载失败: %s", e)
        return None


# ──────────────────────────────────────────────
# 3. MiMo API（远程 fallback）
# ──────────────────────────────────────────────

class MiMoASR:
    """OpenAI 兼容的远程 ASR 客户端（MiMo mimo-v2.5-asr）。"""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.api_key) and bool(self.base_url)

    def transcribe(self, audio_bytes: bytes, filename: str) -> str:
        url = f"{self.base_url}/audio/transcriptions"
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            files={"file": (filename, audio_bytes)},
            data={"model": self.model},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("text", "")


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def _resolve_model_path(user_path: str | None, hf_names: list[str]) -> str:
    """
    按优先级查找模型路径：
    1. 用户指定的路径（环境变量）
    2. 项目本地 models/ 目录
    3. HuggingFace 缓存目录（优先用已缓存的，不自动下载）
    4. 返回第一个 HF 模型名（会触发自动下载）
    """
    if user_path and os.path.exists(user_path):
        return user_path

    # 项目本地 models/ 目录
    project_root = Path(__file__).resolve().parent.parent.parent
    local_models = project_root / "models"
    for name in hf_names:
        short = name.split("/")[-1]  # e.g. faster-whisper-small
        candidate = local_models / short
        if candidate.is_dir():
            return str(candidate)

    # HuggingFace 缓存：优先找已缓存的（按 hf_names 优先级，大模型优先）
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    for name in hf_names:
        safe = name.replace("/", "--")
        candidate = cache_dir / f"models--{safe}"
        if candidate.is_dir():
            snapshots = candidate / "snapshots"
            if snapshots.is_dir():
                for snap in snapshots.iterdir():
                    if snap.is_dir():
                        return str(snap)
            return str(candidate)

    # 都没有，返回第一个模型名（会触发自动下载）
    return hf_names[0]


def build_asr(config: Config):
    """
    自动检测并构建 ASR 客户端，优先级：
    1. 本地 faster-whisper
    2. 本地 openai-whisper
    3. MiMo API（远程）
    """
    model_path = os.environ.get("WSNOTE_ASR_MODEL_PATH", "")
    device = os.environ.get("WSNOTE_ASR_DEVICE", "auto")       # auto/cpu/cuda
    compute_type = os.environ.get("WSNOTE_ASR_COMPUTE", "auto") # auto/int8/float16/float32

    # 处理 device=auto：优先用 ctranslate2 检测 CUDA
    if device == "auto":
        try:
            import ctranslate2
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    # 1. 尝试 faster-whisper
    asr = _try_faster_whisper(model_path or None, device, compute_type)
    if asr:
        return asr

    # 2. 尝试 openai-whisper
    asr = _try_openai_whisper(model_path or None)
    if asr:
        return asr

    # 3. fallback 到 MiMo API
    api_key = os.environ.get("WSNOTE_ASR_API_KEY", config.asr_api_key)
    base_url = os.environ.get("WSNOTE_ASR_BASE_URL", config.asr_base_url) \
               or "https://token-plan-cn.xiaomimimo.com/v1"
    model = os.environ.get("WSNOTE_ASR_MODEL", config.asr_model)
    raw_timeout = os.environ.get("WSNOTE_ASR_TIMEOUT", "")
    try:
        timeout = float(raw_timeout) if raw_timeout else config.asr_timeout
    except ValueError:
        timeout = config.asr_timeout
    if not api_key:
        logger.warning("无本地 whisper 也无 ASR key：音频转写将不可用")
        return MiMoASR("", "", model)
    logger.info("使用 MiMo API ASR: %s", base_url)
    return MiMoASR(base_url, api_key, model, timeout)
