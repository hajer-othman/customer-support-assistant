"""Essai manuel de search_policies : quelques questions, les sections trouvées et leur score.

Lancement, depuis backend/ :  python -m scripts.try_search
"""

import time

from app.db.session import SessionLocal
from app.rag.retrieval import search_policies

# (langue de la conversation, question)
QUESTIONS = [
    ("fr", "Puis-je retourner un article après 40 jours ?"),
    ("en", "How long does standard delivery take?"),
    ("fr", "Je me suis trompée d'adresse, je peux la changer une fois le colis expédié ?"),
    ("en", "Do you sell ski socks?"),  # non couverte : on regarde quels scores on obtient
]

PAUSE_SECONDS = 1.1  # le plan gratuit de Mistral limite à environ une requête par seconde


def main() -> None:
    with SessionLocal() as db:
        for number, (language, question) in enumerate(QUESTIONS):
            if number > 0:
                time.sleep(PAUSE_SECONDS)
            print(f"\n[{language}] {question}")
            for hit in search_policies(db, question, language):
                print(f"  {hit.score:.3f}  {hit.document_name} › {hit.section_title}")


if __name__ == "__main__":
    main()