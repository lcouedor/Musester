from dataclasses import dataclass

@dataclass
class Track:
    id: str
    title: str
    artists: str
    album: str
    added_at: str = None

@dataclass
class Decision:
    id: str
    title: str
    match: int
