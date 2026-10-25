"""Calcul des embeddings avec mistral-embed.

C'est le seul fichier qui connaît le fournisseur d'embeddings : pour en changer,
on ne modifie que ce module (et la taille du vecteur dans la base).
"""

import logging
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "mistral-embed"
URL = "https://api.mistral.ai/v1/embeddings"
DIMENSIONS = 1024  # doit correspondre à Vector(1024) dans models.py

BATCH_SIZE = 32  # nombre de textes envoyés par requête
PAUSE_SECONDS = 1.1  # le plan gratuit limite à environ une requête par seconde
MAX_ATTEMPTS = 5
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """Délai avant un nouvel essai : celui indiqué par l'API si elle en donne un, sinon 2, 4, 8..."""
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return float(2 ** (attempt + 1))


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Une requête à l'API pour un lot de textes, avec de nouveaux essais si elle est saturée."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if api_key is None:
        raise RuntimeError("MISTRAL_API_KEY est absente : vérifie ton fichier backend/.env")

    for attempt in range(MAX_ATTEMPTS):
        response = httpx.post(
            URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": MODEL, "input": texts},
            timeout=60,
        )
        if response.status_code == 200:
            data = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in data]
            if len(vectors) != len(texts) or any(len(v) != DIMENSIONS for v in vectors):
                raise RuntimeError("Réponse inattendue de l'API : nombre ou taille de vecteurs incorrects")
            return vectors

        if response.status_code in RETRYABLE_STATUS and attempt < MAX_ATTEMPTS - 1:
            delay = _retry_delay(response, attempt)
            logger.warning("API saturée (code %s), nouvel essai dans %.0f s", response.status_code, delay)
            time.sleep(delay)
            continue

        raise RuntimeError(f"Erreur de l'API Mistral (code {response.status_code}) : {response.text}")

    raise RuntimeError("Nombre maximal d'essais atteint")  # n'est normalement jamais atteint


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Renvoie un vecteur par texte, dans le même ordre. Envoie les textes par lots."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        if start > 0:
            time.sleep(PAUSE_SECONDS)
        batch = texts[start : start + BATCH_SIZE]
        logger.info("Embeddings : textes %d à %d sur %d", start + 1, start + len(batch), len(texts))
        vectors.extend(_embed_batch(batch))
    return vectors


def embed_query(text: str) -> list[float]:
    """Vecteur d'une question de client (utilisé plus tard par search_policies)."""
    return embed_texts([text])[0]