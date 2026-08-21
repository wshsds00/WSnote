from dataclasses import dataclass, field


@dataclass
class Note:
    id: str
    title: str
    tags: list[str] = field(default_factory=list)
    created: str = ""
    updated: str = ""
    content: str = ""


@dataclass
class NoteMeta:
    id: str
    title: str
    tags: list[str]
    created: str
    updated: str
