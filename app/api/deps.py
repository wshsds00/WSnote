from dataclasses import dataclass


@dataclass
class AppState:
    config: object
    note_store: object
    db: object
    ingestor: object
    llm: object
    searcher: object


def state_from_request(request) -> AppState:
    return request.app.state.s
