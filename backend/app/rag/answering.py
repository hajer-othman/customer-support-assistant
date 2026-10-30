"""Répondre à une question de politique : recherche, prompt, génération, lecture de la réponse.

C'est le chemin 1 du design (question de politique, lecture seule). Cette fonction ne touche
pas à la base : elle ne fait que lire les sections et appeler le LLM.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.rag.generation import generate
from app.rag.prompts import (
    NOT_COVERED_MESSAGES,
    PROMPT_VERSION,
    build_messages,
    cited_hits,
    is_not_covered,
)
from app.rag.retrieval import PolicyHit, search_policies


@dataclass(frozen=True)
class Answer:
    text: str  # ce qui est montré au client
    covered: bool  # False si la question n'est pas couverte par les documents
    sources: list[PolicyHit]  # sections citées par le LLM (vérifiées par le code)
    retrieved: list[PolicyHit]  # toutes les sections envoyées au LLM
    model: str
    prompt_version: str
    prompt_tokens: int
    completion_tokens: int


def answer_question(
    db: Session,
    question: str,
    language: str,
    prompt_version: str = PROMPT_VERSION,
) -> Answer:
    """Cherche les sections, interroge le LLM et renvoie la réponse avec ses sources."""
    hits = search_policies(db, question, language)

    if not hits:  # aucune section dans cette langue : inutile d'appeler le LLM
        return Answer(
            text=NOT_COVERED_MESSAGES[language],
            covered=False,
            sources=[],
            retrieved=[],
            model="",
            prompt_version=prompt_version,
            prompt_tokens=0,
            completion_tokens=0,
        )

    result = generate(build_messages(question, language, hits, prompt_version))

    if is_not_covered(result.text):
        text, covered, sources = NOT_COVERED_MESSAGES[language], False, []
    else:
        text, covered, sources = result.text, True, cited_hits(result.text, hits)

    return Answer(
        text=text,
        covered=covered,
        sources=sources,
        retrieved=hits,
        model=result.model,
        prompt_version=prompt_version,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )