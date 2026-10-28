"""Recherche des sections de politique les plus proches d'une question.

C'est la phase « en ligne » du RAG : à chaque question, on transforme le texte en vecteur,
puis on demande à PostgreSQL (pgvector) les sections les plus proches dans la langue voulue.
Ce module ne génère aucune réponse : il renvoie seulement les sections trouvées.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PolicyChunk  # adapte le chemin si models.py est ailleurs
from app.rag.embeddings import embed_query

DEFAULT_TOP_K = 4
SUPPORTED_LANGUAGES = {"fr", "en"}


@dataclass(frozen=True)
class PolicyHit:
    """Une section trouvée, avec de quoi citer la source."""

    document_name: str
    section_title: str
    content: str
    score: float  # similarité cosinus : plus c'est grand, plus la section est proche


def search_policies(
    db: Session, query: str, language: str, k: int = DEFAULT_TOP_K
) -> list[PolicyHit]:
    """Renvoie les k sections les plus proches de la question, dans la langue donnée.

    `language` vient de la conversation (fournie par le code, jamais choisie par le LLM).
    """
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Langue non prise en charge : {language!r}")

    # 1. la question devient un vecteur, avec le même modèle que les sections
    query_vector = embed_query(query)

    # 2. distance cosinus entre ce vecteur et celui de chaque section (opérateur <=>)
    distance = PolicyChunk.embedding.cosine_distance(query_vector)

    # 3. filtre sur la langue, tri de la plus proche à la plus éloignée, on garde k lignes
    statement = (
        select(
            PolicyChunk.document_name,
            PolicyChunk.section_title,
            PolicyChunk.content,
            distance.label("distance"),
        )
        .where(PolicyChunk.language == language)
        .order_by(distance)
        .limit(k)
    )
    rows = db.execute(statement).all()

    # 4. score = 1 - distance, pour qu'un score plus grand veuille dire « plus pertinent »
    return [
        PolicyHit(
            document_name=row.document_name,
            section_title=row.section_title,
            content=row.content,
            score=1 - row.distance,
        )
        for row in rows
    ]