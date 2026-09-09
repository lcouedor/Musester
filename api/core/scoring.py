import logging
from concurrent.futures import ThreadPoolExecutor

from openai import OpenAI

import config
from core.models import Track
from services.embeddings import embed_texts, cosine_similarity, centroid
from services.lastfm import get_track_tags

logger = logging.getLogger(__name__)
_client = OpenAI(api_key=config.GPT_KEY)


def translate_to_english(text: str) -> str:
    """Les tags Last.fm sont quasi toujours en anglais — sans ça, la similarité
    d'embedding capte autant "même langue" que "même sens" (mesuré : un prompt
    FR matchait mieux avec une chanson française hors-sujet qu'avec un morceau
    ambient pourtant pertinent, une fois traduit l'écart redevient net)."""
    try:
        resp = _client.chat.completions.create(
            model=config.GPT_MODEL,
            messages=[
                {"role": "system", "content": "Translate the following music listening-context description to English. Reply with ONLY the translation, no extra text."},
                {"role": "user", "content": text},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("Translation failed, using original text: %s", e)
        return text


def _track_profile_text(track: Track) -> str:
    primary_artist = track.artists.split('-')[0].strip()
    tags = get_track_tags(primary_artist, track.title)
    if not tags:
        return ""
    return f"{track.title} by {primary_artist}. Tags: {', '.join(tags)}"


class ScoringResult:
    def __init__(self, scores: dict[str, float | None], threshold: float):
        self.scores    = scores     # track_id -> cosine similarity, ou None si pas de tags
        self.threshold = threshold  # calibré sur les ancres

    def passes(self, track_id: str) -> bool:
        s = self.scores.get(track_id)
        return s is not None and s >= self.threshold

    def unscored_ids(self) -> list[str]:
        """Morceaux sans tags Last.fm — aucun signal, à traiter par l'ancien chemin GPT."""
        return [tid for tid, s in self.scores.items() if s is None]


def _combined_score(prompt_vec: list[float], reference_vec: list[float], vec: list[float]) -> float | None:
    if not vec:
        return None
    parts = []
    if prompt_vec:
        parts.append(cosine_similarity(prompt_vec, vec))
    if reference_vec:
        parts.append(cosine_similarity(reference_vec, vec))
    return sum(parts) / len(parts) if parts else None


def score_against_anchors(tracks: list[Track], prompt: str, anchors: list[Track]) -> ScoringResult:
    """Similarité de chaque morceau au prompt + au profil des ancres, avec un
    seuil calibré sur les ancres elles-mêmes plutôt qu'une constante arbitraire :
    le seuil = la similarité de l'ancre la plus "excentrée" par rapport aux
    autres, avec une petite marge — un candidat qui matche moins bien que ça
    matche moins bien que ce que l'utilisateur a lui-même désigné comme
    correspondant exactement à ce qu'il veut.

    Calibration en leave-one-out : chaque ancre est comparée au centroïde des
    AUTRES ancres (jamais elle-même), sinon la comparaison est circulaire —
    une ancre comparée à une référence qui l'inclut déjà se ressemble
    artificiellement, ce qui gonfle le seuil bien au-dessus de ce qu'un vrai
    candidat externe peut atteindre (bug constaté en test : seuil à 0.80 alors
    que les bons candidats plafonnaient à 0.60).
    """
    prompt_en = translate_to_english(prompt)

    with ThreadPoolExecutor(max_workers=8) as ex:
        track_profiles  = list(ex.map(_track_profile_text, tracks))
        anchor_profiles = list(ex.map(_track_profile_text, anchors))

    texts   = [prompt_en] + track_profiles + anchor_profiles
    vectors = embed_texts(texts)

    prompt_vec  = vectors[0]
    track_vecs  = vectors[1 : 1 + len(tracks)]
    anchor_vecs = vectors[1 + len(tracks):]

    anchor_centroid = centroid(anchor_vecs)

    anchor_self_scores = []
    for i, vec in enumerate(anchor_vecs):
        if not vec:
            continue
        others   = anchor_vecs[:i] + anchor_vecs[i + 1:]
        loo_ref  = centroid(others) if others else anchor_centroid
        s = _combined_score(prompt_vec, loo_ref, vec)
        if s is not None:
            anchor_self_scores.append(s)

    threshold = (min(anchor_self_scores) - 0.03) if anchor_self_scores else 0.3

    scores = {
        track.id: _combined_score(prompt_vec, anchor_centroid, vec)
        for track, vec in zip(tracks, track_vecs)
    }

    logger.info(
        "Scoring: %d/%d morceaux tagués, seuil calibré à %.3f (ancres: %s)",
        sum(1 for s in scores.values() if s is not None), len(tracks), threshold,
        [round(s, 3) for s in anchor_self_scores],
    )
    return ScoringResult(scores, threshold)
