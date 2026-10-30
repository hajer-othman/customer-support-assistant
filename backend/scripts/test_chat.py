"""Diagnostic : quels modèles de chat Mistral ta clé peut-elle utiliser, et avec quelle limite ?

Pour chaque modèle, une toute petite requête (5 tokens en sortie au maximum). Une réponse 429 ne
consomme rien. On lit le code de retour et la limite de requêtes par minute annoncée dans les en-têtes.

Lancement, depuis backend/ :
    python -m scripts.test_chat                          # teste la liste CANDIDATES
    python -m scripts.test_chat ministral-8b-latest      # teste seulement les modèles donnés
"""

import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

URL = "https://api.mistral.ai/v1/chat/completions"
PAUSE_SECONDS = 1.5

CANDIDATES = [
    "mistral-small-latest",
    "mistral-small-2603",
    "ministral-3b-latest",
    "ministral-8b-latest",
    "ministral-14b-latest",
    "mistral-medium-latest",
    "mistral-large-4",
]


def main() -> None:
    api_key = os.getenv("MISTRAL_API_KEY")
    if api_key is None:
        raise SystemExit("MISTRAL_API_KEY est absente : vérifie ton fichier backend/.env")
    headers = {"Authorization": f"Bearer {api_key}"}
    models = sys.argv[1:] or CANDIDATES

    for number, model in enumerate(models):
        if number > 0:
            time.sleep(PAUSE_SECONDS)
        response = httpx.post(
            URL,
            headers=headers,
            json={"model": model, "messages": [{"role": "user", "content": "Say OK."}], "max_tokens": 5},
            timeout=60,
        )
        limit = response.headers.get("x-ratelimit-limit-req-minute", "?")
        remaining = response.headers.get("x-ratelimit-remaining-req-minute", "?")
        line = f"{model:<24} code {response.status_code}   requêtes/minute : limite {limit}, restant {remaining}"
        if response.status_code == 200:
            line += f"   réponse : {response.json()['choices'][0]['message']['content']!r}"
        elif response.status_code != 429:
            line += f"   {response.text[:150]}"
        print(line)


if __name__ == "__main__":
    main()