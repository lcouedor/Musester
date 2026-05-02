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
    include: bool
    reason: str = ""

    def __post_init__(self):
        # GPT peut retourner un string "true"/"false"
        if isinstance(self.include, str):
            self.include = self.include.lower() == "true"
