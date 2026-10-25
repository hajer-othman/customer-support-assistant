"""Ingestion des documents de politique : fichiers -> chunks -> embeddings -> table policy_chunks.

La fonction peut être relancée sans risque : une section dont le texte n'a pas changé
n'est ni recalculée ni dupliquée.
"""

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import PolicyChunk
from app.rag.chunking import POLICIES_DIR, Chunk, load_chunks
from app.rag.embeddings import embed_texts

Key = tuple[str, str, str]  # (document_name, language, section_title)


@dataclass
class ChangePlan:
    to_add: list[Chunk] = field(default_factory=list)
    to_update: list[Chunk] = field(default_factory=list)
    unchanged: int = 0
    to_delete: list[Key] = field(default_factory=list)


@dataclass
class IngestionSummary:
    read: int
    added: int
    updated: int
    unchanged: int
    deleted: int


def plan_changes(chunks: list[Chunk], existing: dict[Key, str]) -> ChangePlan:
    """Compare les chunks des fichiers avec ceux de la base (clé -> empreinte).

    Fonction pure : elle ne touche ni la base ni l'API, donc elle se teste facilement.
    """
    plan = ChangePlan()
    for chunk in chunks:
        stored_hash = existing.get(chunk.key)
        if stored_hash is None:
            plan.to_add.append(chunk)
        elif stored_hash != chunk.content_hash:
            plan.to_update.append(chunk)
        else:
            plan.unchanged += 1

    wanted_keys = {chunk.key for chunk in chunks}
    plan.to_delete = [key for key in existing if key not in wanted_keys]
    return plan


def ingest_policies(session: Session, policies_dir: Path = POLICIES_DIR) -> IngestionSummary:
    chunks = load_chunks(policies_dir)
    if not chunks:
        # garde-fou : un dossier introuvable ou vide ne doit pas vider la table
        raise RuntimeError(f"Aucun chunk trouvé dans {policies_dir}")

    rows = session.execute(
        select(
            PolicyChunk.document_name,
            PolicyChunk.language,
            PolicyChunk.section_title,
            PolicyChunk.content_hash,
        )
    ).all()
    existing = {(r.document_name, r.language, r.section_title): r.content_hash for r in rows}

    plan = plan_changes(chunks, existing)

    # Les embeddings sont calculés AVANT de toucher la base : si l'API échoue, la base reste intacte.
    to_write = plan.to_add + plan.to_update

    if to_write:
        vectors = embed_texts([chunk.embedding_text for chunk in to_write])
        values = [
            {
                "id": uuid.uuid4(),
                "document_name": chunk.document_name,
                "language": chunk.language,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "content_hash": chunk.content_hash,
                "embedding": vector,
            }
            for chunk, vector in zip(to_write, vectors)
        ]
        statement = insert(PolicyChunk).values(values)
        # upsert : insère la section, ou met à jour la ligne existante (même clé d'unicité)
        statement = statement.on_conflict_do_update(
            constraint="uq_policy_chunks_section",
            set_={
                "content": statement.excluded.content,
                "content_hash": statement.excluded.content_hash,
                "embedding": statement.excluded.embedding,
            },
        )
        session.execute(statement)

    for document_name, language, section_title in plan.to_delete:
        session.execute(
            delete(PolicyChunk).where(
                PolicyChunk.document_name == document_name,
                PolicyChunk.language == language,
                PolicyChunk.section_title == section_title,
            )
        )

    session.commit()
    return IngestionSummary(
        read=len(chunks),
        added=len(plan.to_add),
        updated=len(plan.to_update),
        unchanged=plan.unchanged,
        deleted=len(plan.to_delete),
    )