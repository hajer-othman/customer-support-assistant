"""Appel au LLM de génération (API de chat de Mistral).

C'est le seul fichier qui connaît le fournisseur de génération : pour en changer
(par exemple pour Groq), on ne modifie que ce module.
"""

import logging
import os
import time
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MODEL = "ministral-14b-2512"
URL = "https://api.mistral.ai/v1/chat/completions"

TEMPERATURE = 0.0  # réponses factuelles et reproductibles
MAX_TOKENS = 400  # longueur maximale de la réponse
RANDOM_SEED = 42  # rend les appels répétés le plus reproductibles possible

# Limite observée pour ce modèle : 30 requêtes par minute, soit une toutes les 2 secondes.
MIN_SECONDS_BETWEEN_CALLS = 2.1

MAX_ATTEMPTS = 5
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str  # modèle réellement utilisé, renvoyé par l'API
    prompt_tokens: int
    completion_tokens: int


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """Délai avant un nouvel essai : celui indiqué par l'API si elle en donne un, sinon 2, 4, 8..."""
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return float(2 ** (attempt + 1))


def _parse(data: dict) -> GenerationResult:
    """Extrait le texte et les compteurs de tokens de la réponse de l'API."""
    choice = data["choices"][0]
    content = choice["message"]["content"]
    if isinstance(content, list):  # certains modèles renvoient une liste de morceaux de texte
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if choice.get("finish_reason") == "length":
        logger.warning("Réponse coupée : MAX_TOKENS (%d) atteint", MAX_TOKENS)
    usage = data.get("usage", {})
    return GenerationResult(
        text=content.strip(),
        model=data.get("model", MODEL),
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
    )


_last_call_time = 0.0


def _wait_for_turn() -> None:
    """Espace les appels pour respecter la limite de requêtes par minute du modèle."""
    global _last_call_time
    wait = MIN_SECONDS_BETWEEN_CALLS - (time.monotonic() - _last_call_time)
    if wait > 0:
        time.sleep(wait)
    _last_call_time = time.monotonic()


def generate(messages: list[dict]) -> GenerationResult:
    """Envoie les messages (system puis user) au LLM et renvoie sa réponse, avec de nouveaux essais si l'API est saturée."""
    api_key = os.getenv("MISTRAL_API_KEY")
    if api_key is None:
        raise RuntimeError("MISTRAL_API_KEY est absente : vérifie ton fichier backend/.env")

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "random_seed": RANDOM_SEED,
    }
    for attempt in range(MAX_ATTEMPTS):
        _wait_for_turn()
        response = httpx.post(
            URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=60,
        )
        if response.status_code == 200:
            return _parse(response.json())

        if response.status_code in RETRYABLE_STATUS and attempt < MAX_ATTEMPTS - 1:
            delay = _retry_delay(response, attempt)
            logger.warning("API saturée (code %s), nouvel essai dans %.0f s", response.status_code, delay)
            time.sleep(delay)
            continue

        raise RuntimeError(f"Erreur de l'API Mistral (code {response.status_code}) : {response.text}")

    raise RuntimeError("Nombre maximal d'essais atteint")  # n'est normalement jamais atteint