from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore
from core.models import Track, Decision
import config
import time
import json

PREPROMPT = """
You are a music classification assistant.

You will receive:
- A textual description of a musical mood, theme, or intent.
- A list of songs, each with an ID, title, artist(s), and album.

Your task:
For each song, return a match percentage (0-100) representing how well it fits the description.

You can rely on: title, artist style, lyrics (if known), album context.
If you don't know a song, return match: 0.

Respond ONLY with a JSON array, no extra text:
[
  {"id": "id1", "title": "title1", "match": 85},
  {"id": "id2", "title": "title2", "match": 10}
]
"""

class ClassifierService:
    def __init__(self):
        self.client = OpenAI(api_key=config.GPT_KEY)
        # Semaphore pour limiter le débit et éviter le rate limit
        self._semaphore = Semaphore(config.MAX_WORKERS)

    def classify(self, description: str, tracks: list[Track]) -> list[Decision]:
        batches = [tracks[i:i+config.BATCH_SIZE] for i in range(0, len(tracks), config.BATCH_SIZE)]
        total = len(batches)
        results = [None] * total

        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            futures = {
                executor.submit(self._process_batch, description, batch, i, total): i
                for i, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()

        return [Decision(**d) for batch in results if batch for d in batch]

    def _process_batch(self, description: str, batch: list[Track], idx: int, total: int) -> list[dict]:
        with self._semaphore:
            prompt = f"Description: {description}\nSongs:\n"
            prompt += "\n".join(
                f"- ID: {t.id}, Title: {t.title}, Artist(s): {t.artists}, Album: {t.album}"
                for t in batch
            )

            for attempt in range(5):
                try:
                    response = self.client.chat.completions.create(
                        model=config.GPT_MODEL,
                        messages=[
                            {"role": "system", "content": PREPROMPT},
                            {"role": "user", "content": prompt},
                        ],
                    )
                    result = json.loads(response.choices[0].message.content)
                    print(f"✅ Batch {idx+1}/{total} ({len(batch)} tracks)")
                    return result
                except json.JSONDecodeError:
                    print(f"⚠️ JSON error on batch {idx+1}, retry {attempt+1}")
                    time.sleep(1)
                except Exception as e:
                    delay = 2 ** attempt
                    print(f"⚠️ Error on batch {idx+1}: {e}. Retry in {delay}s")
                    time.sleep(delay)

            print(f"❌ Batch {idx+1} failed after 5 attempts")
            return []
