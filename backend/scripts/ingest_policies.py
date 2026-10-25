"""Charge les documents de politique dans la table policy_chunks, embeddings compris.

À lancer depuis le dossier backend, comme seed.py :

    python -m scripts.ingest_policies

Le script peut être relancé sans risque : seules les sections nouvelles ou modifiées
sont recalculées, et les sections supprimées des fichiers sont retirées de la base.
"""

import logging

from app.db.session import SessionLocal
from app.rag.ingestion import ingest_policies


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # une ligne par requête : trop bavard

    with SessionLocal() as session:
        summary = ingest_policies(session)

    print(
        f"{summary.read} sections lues : {summary.added} ajoutées, "
        f"{summary.updated} modifiées, {summary.unchanged} inchangées, "
        f"{summary.deleted} supprimées."
    )


if __name__ == "__main__":
    main()