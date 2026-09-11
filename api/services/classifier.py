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
"""

PREPROMPT_PASS1 = """
You are doing a broad first-pass filter for a music playlist.

Be INCLUSIVE: include a song if there is any reasonable chance it could fit the listening context.
Only exclude songs that are clearly and obviously incompatible with the mood described.

Rules:
- If you don't know the song, exclude it (include: false)
- When in doubt, include it — the goal is to keep candidates, not miss them
- Provide a short reason (max 10 words) to justify your choice
"""

PREPROMPT_PASS2 = """
You are a music curator doing a final, selective pass on pre-filtered candidates.

These songs have already passed a broad first filter — they are plausible candidates.
Now be SELECTIVE: only include songs that genuinely and strongly match the listening context.
Reject borderline cases. A focused playlist is better than an exhaustive one.

Rules:
- If you don't know the song, exclude it (include: false)
- Provide a short reason (max 10 words) to justify your choice
"""

PREPROMPT_MULTI = """
You are a music curator building multiple cohesive playlists simultaneously from the same source.

You will receive several playlist descriptions and a list of songs.
For each song, decide which playlists it belongs to — evaluate independently against each.

Rules:
- If you don't know the song, exclude it from all playlists (include: false)
- Be selective per playlist — a focused playlist is better than an exhaustive one
- Provide a short reason (max 10 words) per playlist decision
"""


# Structured Outputs — la sortie n'était garantie que par une consigne dans le
# texte du prompt ("Respond ONLY with a JSON array"), avec un retry sur
# json.JSONDecodeError comme unique filet. Le schéma strict élimine cette
# classe d'erreurs entièrement (root doit être un objet, d'où le wrapping
# "decisions" — déballé juste après l'appel, le reste du code ne voit aucune
# différence).
_DECISIONS_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "track_decisions",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "decisions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id":      {"type": "string"},
                            "title":   {"type": "string"},
                            "include": {"type": "boolean"},
                            "reason":  {"type": "string"},
                        },
                        "required": ["id", "title", "include", "reason"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["decisions"],
            "additionalProperties": False,
        },
    },
}


def _multi_decisions_schema(playlist_indices: list[int]) -> dict:
    """Même principe que _DECISIONS_SCHEMA, mais chaque morceau porte une
    décision par playlist. Les clés de "decisions" doivent être fixes pour un
    schéma strict — construites dynamiquement ici à partir des index réels de
    CETTE requête (au plus 3, la route /generate refuse au-delà)."""
    decision_props = {
        str(i): {
            "type": "object",
            "properties": {"include": {"type": "boolean"}, "reason": {"type": "string"}},
            "required": ["include", "reason"],
            "additionalProperties": False,
        }
        for i in playlist_indices
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "multi_track_decisions",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "tracks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id":        {"type": "string"},
                                "title":     {"type": "string"},
                                "decisions": {
                                    "type": "object",
                                    "properties": decision_props,
                                    "required": [str(i) for i in playlist_indices],
                                    "additionalProperties": False,
                                },
                            },
                            "required": ["id", "title", "decisions"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["tracks"],
                "additionalProperties": False,
            },
        },
    }


class ClassifierService:
    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._client = OpenAI(api_key=config.GPT_KEY)
        return cls._instance

    def generate_description(self, prompt: str) -> str:
        """Description Spotify courte écrite à la génération — pour que la
        playlist se comprenne d'elle-même même consultée hors de Musester."""
        try:
            response = self._client.chat.completions.create(
                model=config.GPT_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Rewrite this playlist request into a short, natural playlist description "
                        "(max 200 characters). No quotes, no hashtags, no emoji. Keep the original language."
                    )},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content.strip()[:300]
        except Exception as e:
            logger.warning("Description generation failed, falling back to raw prompt: %s", e)
            return prompt[:300]

    def _process_batch(
        self,
        description: str,
        batch: list[Track],
        idx: int,
        total: int,
        preprompt: str = None,
        anchors: list[Track] = None,
        languages: dict[str, str] = None,
    ) -> list[dict]:
        if preprompt is None:
            preprompt = PREPROMPT

        if anchors:
            anchor_ids = {a.id for a in anchors}
            batch = sorted(batch, key=lambda t: 0 if t.id in anchor_ids else 1)

        prompt = f"Listening context: {description}\n"

        if anchors:
            prompt += "\nReference tracks — these songs perfectly embody what this playlist should be:\n"
            prompt += "\n".join(f'- "{a.title}" by {a.artists}' for a in anchors)
            prompt += (
                "\nFor each song below, ask: would it feel natural in the same playlist as these reference tracks? "
                "Judge on shared mood, energy, tempo and style — not just the description above.\n"
            )

        if languages:
            prompt += (
                "\nSome songs include a detected sung language (from actual lyrics, not the artist's "
                "nationality) — trust it over any assumption.\n"
            )

        prompt += "\nSongs to evaluate:\n"
        prompt += "\n".join(
            f"- ID: {t.id}, Title: {t.title}, Artist(s): {t.artists}, Album: {t.album}"
            + (f", Detected sung language: {languages[t.id]}" if languages and languages.get(t.id) else "")
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
                    response_format=_DECISIONS_SCHEMA,
                )
                result = json.loads(response.choices[0].message.content)["decisions"]
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
        all_anchor_ids = {a.id for p in playlists_spec for a in (p.get("anchors") or [])}
        sorted_batch   = sorted(batch, key=lambda t: 0 if t.id in all_anchor_ids else 1)

        prompt = "Playlists to fill:\n"
        for p in playlists_spec:
            prompt += f'\n[{p["idx"]}] Context: {p["prompt"]}'
            if p.get("anchors"):
                examples = ", ".join(f'"{a.title}" by {a.artists}' for a in p["anchors"])
                prompt += (
                    f"\n    Reference tracks (they perfectly embody this playlist): {examples}"
                    f"\n    Ask for each candidate: would it feel natural alongside these tracks?"
                )

        prompt += "\n\nSongs to evaluate:\n"
        prompt += "\n".join(
            f"- ID: {t.id}, Title: {t.title}, Artist(s): {t.artists}, Album: {t.album}"
            for t in sorted_batch
        )

        empty  = {p["idx"]: [] for p in playlists_spec}
        schema = _multi_decisions_schema([p["idx"] for p in playlists_spec])

        for attempt in range(5):
            try:
                response = self._client.chat.completions.create(
                    model=config.GPT_MODEL,
                    messages=[
                        {"role": "system", "content": PREPROMPT_MULTI},
                        {"role": "user",   "content": prompt},
                    ],
                    response_format=schema,
                )
                raw = json.loads(response.choices[0].message.content)["tracks"]

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
