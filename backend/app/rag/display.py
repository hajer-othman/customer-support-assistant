"""Mise en forme de la réponse du LLM avant de l'envoyer au client."""

from app.rag.prompts import CITATION_PATTERN
from app.rag.retrieval import PolicyHit


def clean_answer(text: str, hits: list[PolicyHit]) -> str:
    """Prépare le texte affiché au client.

    - retire le gras markdown (**) ;
    - renumérote les citations dans l'ordre d'apparition (1, 2, 3...), pour qu'elles
      correspondent à la liste de sources affichée (même ordre que cited_hits) ;
    - supprime les numéros qui n'existent pas dans les sections envoyées.
    """
    new_numbers: dict[int, int] = {}

    def renumber(match) -> str:
        parts = []
        for part in match.group(1).split(","):
            old = int(part)
            if not 1 <= old <= len(hits):
                continue
            if old not in new_numbers:
                new_numbers[old] = len(new_numbers) + 1
            parts.append(f"[{new_numbers[old]}]")
        return "".join(parts)

    return CITATION_PATTERN.sub(renumber, text.replace("**", ""))