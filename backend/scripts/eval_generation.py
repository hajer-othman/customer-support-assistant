"""Évaluation de la génération, première étape : comportement, sources et tokens (sans juge).

Pour chaque question (les 100 du jeu de test + 6 hors sujet), on lance answer_question et on vérifie :
- le comportement : répond-il quand il faut, dit-il « non couvert » quand il faut ?
- les sources : la réponse cite-t-elle au moins une section, et du bon document ?
- les tokens consommés.
Cette étape NE vérifie PAS que le contenu de la réponse est juste : c'est l'étape suivante.
Toutes les réponses sont enregistrées pour pouvoir les relire.

Lancement, depuis backend/ (environ 6 minutes, à cause de la limite de 30 requêtes par minute) :
    python -m scripts.eval_generation                    # prompt par défaut
    python -m scripts.eval_generation --prompt=v2       # une autre version du prompt
    python -m scripts.eval_generation --resume          # reprend après une interruption
    python -m scripts.eval_generation --reuse           # recalcule les tableaux sans appeler l'API
    python -m scripts.eval_generation --show=Q18        # détail d'une question : réponse, sources, sections envoyées
"""

import json
import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.rag.answering import answer_question
from app.rag.prompts import PROMPT_VERSION

EVAL_DIR = Path(__file__).resolve().parent.parent / "tests" / "eval"
QUESTIONS_FILE = EVAL_DIR / "policy_questions.json"

ANSWERABLE_CATEGORIES = ["direct", "reformulated", "cross", "application"]
NOT_ANSWERABLE_CATEGORIES = ["not_covered", "off_topic"]

OFF_TOPIC_ANSWER = "The question has nothing to do with the shop. The assistant says it does not have this information."


def off_topic(number: int, language: str, question: str) -> dict:
    return {
        "id": f"H{number}",
        "language": language,
        "category": "off_topic",
        "question": question,
        "answerable": False,
        "expected_documents": [],
        "expected_answer": OFF_TOPIC_ANSWER,
    }


OFF_TOPIC_QUESTIONS = [
    off_topic(1, "fr", "Quelle est la recette des pâtes carbonara ?"),
    off_topic(2, "fr", "Quel temps fera-t-il demain à Paris ?"),
    off_topic(3, "fr", "Peux-tu me conseiller un hôtel à Lisbonne ?"),
    off_topic(4, "en", "What is the capital of Australia?"),
    off_topic(5, "en", "How do I fix a flat bicycle tire?"),
    off_topic(6, "en", "Can you recommend a good movie to watch tonight?"),
]


def run_answers(questions: list[dict], version: str, results_file: Path, resume: bool) -> list[dict]:
    """Lance answer_question sur chaque question ; enregistre après chaque réponse."""
    results: list[dict] = []
    if resume and results_file.exists():
        results = json.loads(results_file.read_text(encoding="utf-8"))
    done = {result["id"] for result in results}

    with SessionLocal() as db:
        for number, question in enumerate(questions, start=1):
            if question["id"] in done:
                continue
            try:
                answer = answer_question(db, question["question"], question["language"], prompt_version=version)
            except RuntimeError as error:
                print(f"{number}/{len(questions)}  {question['id']}  ERREUR : {error}")
                continue
            results.append(
                {
                    **question,
                    "answer": answer.text,
                    "covered": answer.covered,
                    "sources": [{"document": h.document_name, "section": h.section_title} for h in answer.sources],
                    "retrieved": [
                        {"document": h.document_name, "section": h.section_title, "score": h.score}
                        for h in answer.retrieved
                    ],
                    "model": answer.model,
                    "prompt_version": answer.prompt_version,
                    "prompt_tokens": answer.prompt_tokens,
                    "completion_tokens": answer.completion_tokens,
                }
            )
            results_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{number}/{len(questions)}  {question['id']}")

    missing = len(questions) - len(results)
    if missing:
        print(f"\n{missing} question(s) sans réponse (erreurs) : relance avec --resume")
    return results


def percent(count: int, total: int) -> str:
    return f"{100 * count / total:.0f} %" if total else "-"


def print_behaviour(results: list[dict]) -> None:
    print("\nQuestions couvertes : le système répond-il ?")
    print(f"{'catégorie':<14}{'n':>4}{'répond':>9}{'refuse à tort':>16}")
    answerable = [r for r in results if r["answerable"]]
    for category in ANSWERABLE_CATEGORIES + ["total"]:
        rows = answerable if category == "total" else [r for r in answerable if r["category"] == category]
        answered = sum(r["covered"] for r in rows)
        print(f"{category:<14}{len(rows):>4}{percent(answered, len(rows)):>9}{percent(len(rows) - answered, len(rows)):>16}")

    print("\nQuestions non couvertes ou hors sujet : le système dit-il « non couvert » ?")
    print(f"{'catégorie':<14}{'n':>4}{'refuse (correct)':>18}{'répond à tort':>15}")
    for category in NOT_ANSWERABLE_CATEGORIES:
        rows = [r for r in results if r["category"] == category]
        refused = sum(not r["covered"] for r in rows)
        print(f"{category:<14}{len(rows):>4}{percent(refused, len(rows)):>18}{percent(len(rows) - refused, len(rows)):>15}")


def print_citations(results: list[dict]) -> None:
    answered = [r for r in results if r["answerable"] and r["covered"]]
    with_source = [r for r in answered if r["sources"]]
    right_document = [
        r for r in with_source if {s["document"] for s in r["sources"]} & set(r["expected_documents"])
    ]
    print(f"\nSources (sur les {len(answered)} questions couvertes auxquelles le système répond)")
    print(f"  au moins une section citée : {len(with_source)} / {len(answered)} ({percent(len(with_source), len(answered))})")
    print(f"  dont un document attendu   : {len(right_document)} / {len(answered)} ({percent(len(right_document), len(answered))})")


def print_tokens(results: list[dict]) -> None:
    prompt_total = sum(r["prompt_tokens"] for r in results)
    completion_total = sum(r["completion_tokens"] for r in results)
    count = len(results)
    print(f"\nTokens : {prompt_total} en entrée ({prompt_total // count} par question), "
          f"{completion_total} en sortie ({completion_total // count} par question)")


def snippet(text: str, length: int = 140) -> str:
    flat = text.replace("\n", " ")
    return flat if len(flat) <= length else flat[:length] + "..."


def print_issues(results: list[dict]) -> None:
    groups = [
        ("Questions couvertes refusées à tort", [r for r in results if r["answerable"] and not r["covered"]]),
        ("Questions non couvertes ou hors sujet auxquelles le système répond", [r for r in results if not r["answerable"] and r["covered"]]),
        ("Réponses sans aucune source citée", [r for r in results if r["answerable"] and r["covered"] and not r["sources"]]),
        (
            "Réponses dont les sources citées ne contiennent aucun document attendu",
            [
                r
                for r in results
                if r["answerable"]
                and r["covered"]
                and r["sources"]
                and not ({s["document"] for s in r["sources"]} & set(r["expected_documents"]))
            ],
        ),
    ]
    for title, rows in groups:
        print(f"\n{title} ({len(rows)})")
        for r in rows:
            print(f"  {r['id']} [{r['category']}] {r['question']}")
            print(f"      -> {snippet(r['answer'])}")


def show_one(results: list[dict], question_id: str) -> None:
    """Affiche le détail d'une question : réponse attendue, réponse du système, sources et sections envoyées au LLM."""
    for r in results:
        if r["id"] == question_id:
            print(f"\n{r['id']} [{r['category']}] {r['question']}")
            print(f"documents attendus : {r['expected_documents']}")
            print(f"réponse attendue   : {r['expected_answer']}")
            print(f"réponse du système : {r['answer']}")
            print(f"couverte : {'oui' if r['covered'] else 'non'}")
            print("sources citées :", ", ".join(f"{s['document']} › {s['section']}" for s in r["sources"]) or "aucune")
            print("sections envoyées au LLM :")
            for number, hit in enumerate(r["retrieved"], start=1):
                print(f"  [{number}] {hit['score']:.3f}  {hit['document']} › {hit['section']}")
            return
    print(f"{question_id} introuvable dans les résultats")


def main() -> None:
    version = PROMPT_VERSION
    for argument in sys.argv[1:]:
        if argument.startswith("--prompt="):
            version = argument.split("=", 1)[1]
    results_file = EVAL_DIR / f"generation_results_{version}.json"

    for argument in sys.argv[1:]:
        if argument.startswith("--show="):
            show_one(json.loads(results_file.read_text(encoding="utf-8")), argument.split("=", 1)[1])
            return

    if "--reuse" in sys.argv:
        results = json.loads(results_file.read_text(encoding="utf-8"))
    else:
        questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8")) + OFF_TOPIC_QUESTIONS
        results = run_answers(questions, version, results_file, resume="--resume" in sys.argv)
        print(f"\nRéponses enregistrées dans {results_file}")

    print(f"\nPrompt {version}, modèle {results[0]['model']}")
    print_behaviour(results)
    print_citations(results)
    print_tokens(results)
    print_issues(results)


if __name__ == "__main__":
    main()