from app.core.config import Config, get_config


def test_config_defaults_and_dirs():
    cfg = get_config()
    assert cfg.chunk_size > 0
    assert cfg.embedding_dim == 512
    assert cfg.notes_dir.name == "notes"
    assert cfg.data_dir.exists()  # 目录被自动创建
