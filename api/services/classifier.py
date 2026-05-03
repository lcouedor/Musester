import json
import logging
import time

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
  {"id": "...", "title": "...", "include": true,  "reason": "Downtempo, fits focused late-night work"},
  {"id": "...", "title": "...", "include": false, "reason": "Too energetic, breaks the mood"}
]
"""

PREPROMPT_PASS1 = """
You are doing a broad first-pass filter for a music playlist.

Be INCLUSIVE: include a song if there is any reasonable chance it could fit the listening context.
Only exclude songs that are clearly and obviously incompatible with the mood described.

Rules:
- If you don't know the song, exclude it (include: false)
- When in doubt, include it — the goal is to keep candidates, not miss them
- Provide a short reason (max 10 words) to justify your choice

Respond ONLY with a JSON array, no extra text:
[
  {"id": "...", "title": "...", "include": true,  "reason": "Could fit the mood"},
  {"id": "...", "title": "...", "include": false, "reason": "Clearly incompatible energy"}
]
"""

PREPROMPT_PASS2 = """
You are a music curator doing a final, selective pass on pre-filtered candidates.

These songs have already passed a broad first filter — they are plausible candidates.
Now be SELECTIVE: only include songs that genuinely and strongly match the listening context.
Reject borderline cases. A focused playlist is better than an exhaustive one.

Rules:
- If you don't know the song, exclude it (include: false)
- Provide a short reason (max 10 words) to justify your choice

Respond ONLY with a JSON array, no extra text:
[
  {"id": "...", "title": "...", "include": true,  "reason": "Perfect fit for the described mood"},
  {"id": "...", "title": "...", "include": false, "reason": "Too generic, doesn't commit to the vibe"}
]
"""

PREPROMPT_MULTI = """
You are a music curator building multiple cohesive playlists simultaneously from the same source.

You will receive several playlist descriptions and a list of songs.
For each song, decide which playlists it belongs to — evaluate independently against each.

Rules:
- If you don't know the song, exclude it from all playlists (include: false)
- Be selective per playlist — a focused playlist is better than an exhaustive one
- Provide a short reason (max 10 words) per playlist decision

Respond ONLY with a JSON array, no extra text:
[
  {
    "id": "...",
    "title": "...",
    "decisions": {
      "0": {"include": true,  "reason": "Downtempo, fits late-night focus"},
      "1": {"include": false, "reason": "Too slow, breaks workout energy"}
    }
  }
]
"""


class ClassifierService:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._client = OpenAI(api_key=config.GPT_KEY)
        return cls._instance

    def _process_batch(
        self,
        description: str,
        batch: list[Track],
        idx: int,
        total: int,
        preprompt: str = None,
        anchors: list[Track] = None,
    ) -> list[dict]:
        if preprompt is None:
            preprompt = PREPROMPT

        prompt = f"Listening context: {description}\n"

        if anchors:
            prompt += "\nReference examples (these songs MUST fit — use them to calibrate your judgment):\n"
            prompt += "\n".join(f'- "{a.title}" by {a.artists}' for a in anchors)
            prompt += "\n"

        prompt += "\nSongs to evaluate:\n"
        prompt += "\n".join(
            f"- ID: {t.id}, Title: {t.title}, Artist(s): {t.artists}, Album: {t.album}"
            for t in batch
        )

        for attempt in range(5):
            try:
                response = self._client.chat.completions.create(
                    model=config.GPT_MODEL,
                    messages=[
                        {"role": "system", "content": preprompt},
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

    def _process_batch_multi(
        self,
        playlists_spec: list[dict],
        batch: list[Track],
        idx: int,
        total: int,
    ) -> dict[int, list[dict]]:
        """
        playlists_spec: [{'idx': int, 'prompt': str, 'anchors': list[Track]}]
        Returns: {playlist_idx: [decision_dicts]}
        """
        prompt = "Playlists to fill:\n"
        for p in playlists_spec:
            prompt += f'\n[{p["idx"]}] Context: {p["prompt"]}'
            if p.get("anchors"):
                examples = ", ".join(f'"{a.title}" by {a.artists}' for a in p["anchors"])
                prompt += f"\n    Reference examples (must fit): {examples}"

        prompt += "\n\nSongs to evaluate:\n"
        prompt += "\n".join(
            f"- ID: {t.id}, Title: {t.title}, Artist(s): {t.artists}, Album: {t.album}"
            for t in batch
        )

        empty = {p["idx"]: [] for p in playlists_spec}

        for attempt in range(5):
            try:
                response = self._client.chat.completions.create(
                    model=config.GPT_MODEL,
                    messages=[
                        {"role": "system", "content": PREPROMPT_MULTI},
                        {"role": "user",   "content": prompt},
                    ],
                )
                raw = json.loads(response.choices[0].message.content)

                result: dict[int, list[dict]] = {p["idx"]: [] for p in playlists_spec}
                for item in raw:
                    for idx_str, dec in item.get("decisions", {}).items():
                        try:
                            pidx = int(idx_str)
                            if pidx in result:
                                result[pidx].append({
                                    "id":      item.get("id", ""),
                                    "title":   item.get("title", ""),
                                    "include": dec.get("include", False),
                                    "reason":  dec.get("reason", ""),
                                })
                        except (ValueError, KeyError):
                            pass

                logger.info("Multi-batch %d/%d OK (%d tracks, %d playlists)",
                            idx + 1, total, len(batch), len(playlists_spec))
                return result

            except json.JSONDecodeError as e:
                logger.warning("Multi-batch %d/%d — JSON parse error: %s", idx + 1, total, e)
                time.sleep(1)
            except Exception as e:
                delay = 2 ** attempt
                logger.warning("Multi-batch %d/%d — API error: %s. Retry in %ds", idx + 1, total, e, delay)
                time.sleep(delay)

        logger.error("Multi-batch %d/%d failed after 5 attempts", idx + 1, total)
        return empty
