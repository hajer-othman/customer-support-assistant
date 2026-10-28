"""Recherche des sections de politique les plus proches d'une question.

C'est la phase « en ligne » du RAG : à chaque question, on transforme le texte en vecteur,
puis on demande à PostgreSQL (pgvector) les sections les plus proches dans la langue voulue.
On garde ensuite k sections avec au plus 2 par document, pour qu'un seul document ne prenne pas
toute la place (cas des questions qui ont besoin de deux documents).
Ce module ne génère aucune réponse : il renvoie seulement les sections trouvées.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PolicyChunk  # adapte le chemin si models.py est ailleurs
from app.rag.embeddings import embed_query

DEFAULT_TOP_K = 4
DEFAULT_MAX_PER_DOCUMENT = 2
CANDIDATE_COUNT = 8  # nombre de sections demandées à la base avant de diversifier
SUPPORTED_LANGUAGES = {"fr", "en"}


@dataclass(frozen=True)
class PolicyHit:
    """Une section trouvée, avec de quoi citer la source."""

    document_name: str
    section_title: str
    content: str
    score: float  # similarité cosinus : plus c'est grand, plus la section est proche


def _diversify(hits: list[PolicyHit], k: int, max_per_document: int) -> list[PolicyHit]:
    """Parcourt les sections dans l'ordre et saute celles d'un document déjà présent `max_per_document` fois."""
    kept: list[PolicyHit] = []
    skipped: list[PolicyHit] = []
    counts: dict[str, int] = {}
    for hit in hits:
        if counts.get(hit.document_name, 0) < max_per_document:
            kept.append(hit)
            counts[hit.document_name] = counts.get(hit.document_name, 0) + 1
            if len(kept) == k:
                return kept
        else:
            skipped.append(hit)
    # pas assez de documents différents : on complète avec les sections sautées, les mieux classées d'abord
    selection = kept + skipped[: k - len(kept)]
    return sorted(selection, key=lambda hit: hit.score, reverse=True)


def search_policies(
    db: Session,
    query: str,
    language: str,
    k: int = DEFAULT_TOP_K,
    max_per_document: int | None = DEFAULT_MAX_PER_DOCUMENT,
) -> list[PolicyHit]:
    """Renvoie k sections proches de la question, dans la langue donnée.

    `language` vient de la conversation (fournie par le code, jamais choisie par le LLM).
    `max_per_document=None` désactive la diversification : on obtient alors les k plus proches, tout simplement.
    """
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Langue non prise en charge : {language!r}")

    # 1. la question devient un vecteur, avec le même modèle que les sections
    query_vector = embed_query(query)

    # 2. distance cosinus entre ce vecteur et celui de chaque section (opérateur <=>)
    distance = PolicyChunk.embedding.cosine_distance(query_vector)

    # 3. filtre sur la langue, tri de la plus proche à la plus éloignée, on garde les candidates
    #    (plus que k quand on diversifie, pour avoir de quoi remplacer les sections sautées)
    limit = k if max_per_document is None else max(CANDIDATE_COUNT, k)
    statement = (
        select(
            PolicyChunk.document_name,
            PolicyChunk.section_title,
            PolicyChunk.content,
            distance.label("distance"),
        )
        .where(PolicyChunk.language == language)
        .order_by(distance)
        .limit(limit)
    )
    rows = db.execute(statement).all()

    # 4. score = 1 - distance, pour qu'un score plus grand veuille dire « plus pertinent »
    hits = [
        PolicyHit(
            document_name=row.document_name,
            section_title=row.section_title,
            content=row.content,
            score=1 - row.distance,
        )
        for row in rows
    ]

    # 5. on garde k sections, avec au plus max_per_document par document
    if max_per_document is None:
        return hits
    return _diversify(hits, k, max_per_document)