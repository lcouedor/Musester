import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore

from openai import OpenAI
from core.models import Track, Decision
import config

logger = logging.getLogger(__name__)

PREPROMPT = """
You are a music curator building a cohesive playlist.

You will receive a listening context description and a list of songs.
For each song, decide whether it belongs in this playlist.

Base your decision on:
- Energy level and tempo
- Mood and emotional tone
- Genre and artist's typical style
- Lyrical themes (if known)
- How well it fits alongside other songs that match the description

Rules:
- If you don't know the song, exclude it (include: false)
- Be selective — a focused playlist is better than an exhaustive one
- Provide a short reason (max 10 words) to justify your choice

Respond ONLY with a JSON array, no extra text:
[
  {"id": "...", "title": "...", "include": true, "reason": "Downtempo, fits focused late-night work"},
  {"id": "...", "title": "...", "include": false, "reason": "Too energetic, breaks the mood"}
]
"""


class ClassifierService:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._client    = OpenAI(api_key=config.GPT_KEY)
            cls._instance._semaphore = Semaphore(config.MAX_WORKERS)
        return cls._instance

    def classify(self, description: str, tracks: list[Track]) -> list[Decision]:
        batches = [tracks[i:i+config.BATCH_SIZE] for i in range(0, len(tracks), config.BATCH_SIZE)]
        total   = len(batches)
        results = [None] * total

        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
            futures = {
                executor.submit(self._process_batch, description, batch, i, total): i
                for i, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                idx          = futures[future]
                results[idx] = future.result()

        decisions = []
        for batch in results:
            if not batch:
                continue
            for d in batch:
                try:
                    decisions.append(Decision(**d))
                except (TypeError, ValueError) as e:
                    logger.warning("Skipping malformed decision %s: %s", d, e)

        logger.info("Classification done: %d decisions", len(decisions))
        return decisions

    def _process_batch(self, description: str, batch: list[Track], idx: int, total: int) -> list[dict]:
        prompt  = f"Listening context: {description}\nSongs:\n"
        prompt += "\n".join(
            f"- ID: {t.id}, Title: {t.title}, Artist(s): {t.artists}, Album: {t.album}"
            for t in batch
        )

        with self._semaphore:
            for attempt in range(5):
                try:
                    response = self._client.chat.completions.create(
                        model=config.GPT_MODEL,
                        messages=[
                            {"role": "system", "content": PREPROMPT},
                            {"role": "user",   "content": prompt},
                        ],
                    )
                    result = json.loads(response.choices[0].message.content)
                    logger.info("Batch %d/%d OK (%d tracks)", idx + 1, total, len(batch))
                    return result
                except json.JSONDecodeError as e:
                    logger.warning("Batch %d/%d — JSON parse error: %s", idx + 1, total, e)
                    time.sleep(1)
                except Exception as e:
                    delay = 2 ** attempt
                    logger.warning("Batch %d/%d — API error: %s. Retry in %ds", idx + 1, total, e, delay)
                    time.sleep(delay)

        logger.error("Batch %d/%d failed after 5 attempts", idx + 1, total)
        return []
