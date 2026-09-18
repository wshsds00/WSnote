import logging
import re
from typing import Iterator

from app.notes.models import Note, NoteMeta

logger = logging.getLogger("wsnote.process")

# 单次 AI 整理的最大文本长度（中文约 6 万字以内）
MAX_CHARS = 60000

_H1 = re.compile(r"^#\s+.*$", re.MULTILINE)
_TITLE_PREFIX = re.compile(r"^#{1,6}\s*")


def _derive_title(text: str) -> str:
    """从文稿首行非空文本推导标题。"""
    for line in text.splitlines():
        line = _TITLE_PREFIX.sub("", line).strip().strip("-*· \t。，；！？、")
        if line:
            return line[:60]
    return "导入笔记"


def _split_h1(markdown: str) -> list[tuple[str, str]]:
    """按一级标题（# ）拆块，返回 [(标题, 正文)]。无一级标题返回 []。"""
    matches = list(_H1.finditer(markdown))
    if not matches:
        return []
    blocks: list[tuple[str, str]] = []
    # 首个一级标题之前的前言
    preface = markdown[: matches[0].start()].strip()
    if preface:
        blocks.append(("前言", preface))
    for i, m in enumerate(matches):
        title = m.group(0)[2:].strip() or "未命名"
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        content = markdown[start:end].strip()
        blocks.append((title, content))
    return blocks


_PROMPTS = {
    "interview": (
        "你是一名面试复盘助手。下面是一份面试过程的录音文字稿，请把它整理成一份结构化的复盘笔记。\n\n"
        "要求：\n"
        "1. 只基于文稿内容，不要编造未提到的信息；\n"
        "2. 用中文，输出为 Markdown；\n"
        "3. 结构固定包含四节：\n"
        "   ## 面试问题与我的回答（逐条列出面试官的问题，以及我当时的回答要点）；\n"
        "   ## 考察知识点（每道题考察的知识点）；\n"
        "   ## 表现复盘（分「答得好的」「卡壳或答得不好的」）；\n"
        "   ## 复习建议（针对薄弱点给出具体建议）。\n\n"
        "文字稿如下：\n{TEXT}"
    ),
    "general": (
        "你是一名知识整理助手。下面是一篇长文稿，请把它整理成一份结构清晰的笔记。\n\n"
        "要求：\n"
        "1. 只基于文稿内容，不要编造未提到的信息；\n"
        "2. 用中文，输出为 Markdown；\n"
        "3. 结构包含：大纲、核心要点（分条列出）、结论与行动项。\n\n"
        "文稿如下：\n{TEXT}"
    ),
    "meeting": (
        "你是一名会议纪要助手。下面是一份会议记录或会议录音文字稿，请整理成规范的会议纪要。\n\n"
        "要求：\n"
        "1. 只基于文稿内容，不要编造；\n"
        "2. 用中文，输出为 Markdown；\n"
        "3. 结构包含：议题、决议、待办（每条注明责任人，能确定的注明时间）。\n\n"
        "文稿如下：\n{TEXT}"
    ),
}


class NoteProcessor:
    """文稿导入 + AI 整理 + 音频转写。"""

    def __init__(self, note_store, ingestor, llm, asr=None):
        self.note_store = note_store
        self.ingestor = ingestor
        self.llm = llm
        self.asr = asr

    def _create_and_index(self, title: str, content: str, tags: list[str]) -> Note | None:
        """建一篇并索引；标题冲突返回 None（调用方记入 skipped）。"""
        try:
            note = self.note_store.create(title, content, tags)
        except FileExistsError:
            return None
        self.ingestor.index_note(note.id)
        return note

    def transcribe_audio(self, audio_bytes: bytes, filename: str) -> str:
        """调用 ASR 转写音频，返回文字稿。"""
        if not self.asr or not self.asr.available():
            raise ValueError("ASR 未配置：请设置环境变量 WSNOTE_ASR_API_KEY")
        return self.asr.transcribe(audio_bytes, filename)

    def import_text(self, text: str, mode: str = "single",
                    title: str = "", tags: list[str] | None = None) -> tuple[list[NoteMeta], list[str]]:
        text = text.strip()
        if not text:
            raise ValueError("文稿为空")
        tags = tags or []
        if mode == "split_h1":
            blocks = _split_h1(text)
            if not blocks:
                blocks = [(_derive_title(text), text)]  # 没有一级标题 → 回落整篇
        else:
            blocks = [(title.strip() or _derive_title(text), text)]

        created: list[NoteMeta] = []
        skipped: list[str] = []
        for t, content in blocks:
            if not content:
                continue
            note = self._create_and_index(t, content, tags)
            if note is None:
                skipped.append(t)
            else:
                created.append(NoteMeta(note.id, note.title, note.tags, note.created, note.updated))
        if not created and not skipped:
            raise ValueError("没有可导入的内容")
        return created, skipped

    def validate_analyze(self, text: str, mode: str) -> str:
        """校验整理入参；非法时抛 ValueError。"""
        text = text.strip()
        if not text:
            raise ValueError("文稿为空")
        if mode not in _PROMPTS:
            raise ValueError(f"未知整理模式: {mode}")
        if len(text) > MAX_CHARS:
            raise ValueError("文稿过长，请分段整理（单次不超过 6 万字）")
        return text

    def analyze_stream(self, text: str, mode: str) -> Iterator[dict]:
        """流式整理，产出事件 dict：meta / delta / error / done。"""
        text = self.validate_analyze(text, mode)
        yield {"type": "meta", "degraded": False, "mode": mode}
        messages = [{"role": "user", "content": _PROMPTS[mode].replace("{TEXT}", text)}]
        received = False
        try:
            for chunk in self.llm.complete_stream(messages):
                if not chunk:
                    continue
                received = True
                yield {"type": "delta", "content": chunk}
        except Exception:
            logger.exception("AI 整理流式调用失败")
            yield {"type": "error", "message": "AI 整理调用失败，请稍后重试"}
            return
        if not received:
            yield {"type": "error", "message": "LLM 返回空内容"}
            return
        yield {"type": "done"}
