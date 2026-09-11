import logging
import math

from openai import OpenAI

import config

logger = logging.getLogger(__name__)
# Un seul appel embarque potentiellement tous les textes d'une grosse
# bibliothèque (1000+ morceaux) — plus généreux que le client de classification,
# mais toujours borné (défaut SDK : 600s, invisible côté SSE jusqu'à échéance).
_client = OpenAI(api_key=config.GPT_KEY, timeout=90)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Vecteurs d'embedding pour une liste de textes, dans le même ordre.
    Un texte vide donne un vecteur nul plutôt qu'un appel API inutile."""
    indices    = [i for i, t in enumerate(texts) if t and t.strip()]
    vectors    = [None] * len(texts)
    if not indices:
        return [[] for _ in texts]

    resp = _client.embeddings.create(
        model=config.EMBEDDING_MODEL,
        input=[texts[i] for i in indices],
    )
    for pos, i in enumerate(indices):
        vectors[i] = resp.data[pos].embedding
    for i in range(len(vectors)):
        if vectors[i] is None:
            vectors[i] = []
    return vectors


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot   = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def centroid(vectors: list[list[float]]) -> list[float]:
    vecs = [v for v in vectors if v]
    if not vecs:
        return []
    dim = len(vecs[0])
    return [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
