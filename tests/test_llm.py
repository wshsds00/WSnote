import tempfile
from pathlib import Path

from app.core.config import Config
from app.core.llm import FakeLLM, build_llm


def test_fake_llm():
    llm = FakeLLM()
    assert llm.available() is True
    assert "回复" in llm.complete([{"role": "user", "content": "hi"}])


def test_build_without_key_degrades():
    d = tempfile.mkdtemp()
    cfg = Config(root_dir=Path(d), notes_dir=Path(d) / "notes", data_dir=Path(d) / "data")
    cfg.llm_api_key = ""
    llm = build_llm(cfg)
    assert llm.available() is False
