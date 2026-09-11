import base64
import logging

from openai import OpenAI

import config

logger = logging.getLogger(__name__)
_client = OpenAI(api_key=config.GPT_KEY)

# Spotify plafonne l'upload de cover à 256 KB — une image ratée ou trop lourde
# ne doit jamais faire échouer la création de la playlist elle-même, d'où le
# None de retour plutôt qu'une exception qui remonterait jusqu'à l'appelant.
_MAX_COVER_BYTES = 256_000


def generate_cover(prompt: str) -> str | None:
    """Cover carrée générée à partir du prompt de la playlist, en JPEG base64
    prêt pour spotify.playlist_upload_cover_image(). None si la génération
    échoue, ou si l'image dépasse la limite Spotify."""
    try:
        result = _client.images.generate(
            model=config.IMAGE_MODEL,
            prompt=(
                "Abstract album/playlist cover art capturing this mood — no text, "
                f"no words, no letters, no logos. Mood: {prompt}"
            ),
            size="1024x1024",
            quality="low",
            output_format="jpeg",
            n=1,
        )
        b64 = result.data[0].b64_json
        if not b64:
            return None
        if len(b64) * 3 / 4 > _MAX_COVER_BYTES:
            logger.warning("Generated cover exceeds Spotify's 256KB limit, skipping")
            return None
        return b64
    except Exception as e:
        logger.warning("Cover generation failed: %s", e)
        return None
