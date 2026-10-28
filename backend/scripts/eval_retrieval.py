"""Mesure du retrieval sur les 100 questions de test.

Pour chaque question, on enregistre les 8 meilleures sections. Ensuite, on SIMULE des k plus petits
en ne regardant que les premiers résultats : une seule série d'appels à l'API suffit pour comparer
k = 3, 4, 5, 6 et 8, et pour tester un top-4 « diversifié » (au plus 2 sections par document).

Lancement, depuis backend/ :
    python -m scripts.eval_retrieval            # lance les 100 recherches (environ 2 à 3 minutes)
    python -m scripts.eval_retrieval --reuse    # recalcule les tableaux à partir du dernier fichier de résultats
"""

import json
import statistics
import sys
import time
from pathlib import Path

from app.db.session import SessionLocal
from app.rag.retrieval import search_policies

EVAL_DIR = Path(__file__).resolve().parent.parent / "tests" / "eval"
QUESTIONS_FILE = EVAL_DIR / "policy_questions.json"
RESULTS_FILE = EVAL_DIR / "retrieval_results.json"

MAX_K = 8  # nombre de résultats enregistrés par question
K_VALUES = (3, 4, 5, 6, 8)  # les valeurs de k comparées
REPORT_K = 4  # k de référence pour la liste des échecs et le top-k diversifié
PER_DOC = 2  # top-k diversifié : au plus 2 sections du même document
PAUSE_SECONDS = 1.1  # limite d'environ une requête par seconde sur le plan gratuit de Mistral
CATEGORIES = ["direct", "reformulated", "cross", "application"]


def run_searches(questions: list[dict]) -> list[dict]:
    """Lance search_policies sur chaque question et garde les résultats bruts."""
    results = []
    with SessionLocal() as db:
        for number, question in enumerate(questions):
            if number > 0:
                time.sleep(PAUSE_SECONDS)
            # max_per_document=None : on enregistre les 8 plus proches, sans diversifier (le script simule la suite)
            hits = search_policies(
                db, question["question"], question["language"], k=MAX_K, max_per_document=None
            )
            results.append(
                {
                    **question,
                    "hits": [
                        {"document": h.document_name, "section": h.section_title, "score": h.score}
                        for h in hits
                    ],
                }
            )
            print(f"{number + 1}/{len(questions)}  {question['id']}")
    return results


def is_top1(result: dict) -> bool:
    """Le premier résultat appartient à un des documents attendus."""
    return result["hits"][0]["document"] in result["expected_documents"]


def covers_expected(result: dict, hits: list[dict]) -> bool:
    """Tous les documents attendus sont présents dans ces résultats (les deux, pour une question croisée)."""
    return set(result["expected_documents"]) <= {hit["document"] for hit in hits}


def is_in_top_k(result: dict, k: int) -> bool:
    return covers_expected(result, result["hits"][:k])


def diversified(hits: list[dict], k: int, per_doc: int = PER_DOC) -> list[dict]:
    """Parcourt les résultats dans l'ordre et garde au plus `per_doc` sections par document, jusqu'à k."""
    kept: list[dict] = []
    counts: dict[str, int] = {}
    for hit in hits:
        if counts.get(hit["document"], 0) < per_doc:
            kept.append(hit)
            counts[hit["document"]] = counts.get(hit["document"], 0) + 1
        if len(kept) == k:
            break
    return kept


def percent(count: int, total: int) -> str:
    return f"{100 * count / total:.0f} %" if total else "-"


def print_hit_table(results: list[dict]) -> None:
    available = len(results[0]["hits"])
    k_values = [k for k in K_VALUES if k <= available]
    answerable = [r for r in results if r["answerable"]]

    print("\nBon document trouvé (questions couvertes)")
    header = f"{'catégorie':<14}{'n':>4}{'top-1':>8}"
    header += "".join(f"{'top-' + str(k):>8}" for k in k_values)
    header += f"{'div-' + str(REPORT_K):>8}"
    print(header)
    for category in CATEGORIES + ["total"]:
        rows = answerable if category == "total" else [r for r in answerable if r["category"] == category]
        line = f"{category:<14}{len(rows):>4}{percent(sum(is_top1(r) for r in rows), len(rows)):>8}"
        for k in k_values:
            line += f"{percent(sum(is_in_top_k(r, k) for r in rows), len(rows)):>8}"
        diversified_count = sum(covers_expected(r, diversified(r["hits"], REPORT_K)) for r in rows)
        line += f"{percent(diversified_count, len(rows)):>8}"
        print(line)
    print(f"  (div-{REPORT_K} : {REPORT_K} résultats, au plus {PER_DOC} sections par document)")


def print_score_table(results: list[dict]) -> None:
    print("\nMeilleur score (top-1), par langue")
    for language in ("fr", "en"):
        for label, covered in (("couvertes", True), ("non couvertes", False)):
            scores = [
                r["hits"][0]["score"]
                for r in results
                if r["language"] == language and r["answerable"] == covered
            ]
            print(
                f"  {language}  {label:<14} n={len(scores):<3} "
                f"min={min(scores):.3f}  médiane={statistics.median(scores):.3f}  max={max(scores):.3f}"
            )


def print_threshold_sweep(results: list[dict]) -> None:
    covered = [r["hits"][0]["score"] for r in results if r["answerable"]]
    not_covered = [r["hits"][0]["score"] for r in results if not r["answerable"]]
    print("\nSeuil sur le meilleur score : erreurs selon la valeur choisie")
    print(f"  {'seuil':<7}{'couvertes rejetées à tort':>28}{'non couvertes acceptées à tort':>34}")
    for hundredths in range(66, 90, 2):
        threshold = hundredths / 100
        rejected = sum(score < threshold for score in covered)
        accepted = sum(score >= threshold for score in not_covered)
        print(f"  {threshold:<7.2f}{f'{rejected} / {len(covered)}':>28}{f'{accepted} / {len(not_covered)}':>34}")


def print_score_extremes(results: list[dict], count: int = 6) -> None:
    covered = sorted((r for r in results if r["answerable"]), key=lambda r: r["hits"][0]["score"])
    not_covered = sorted(
        (r for r in results if not r["answerable"]), key=lambda r: r["hits"][0]["score"], reverse=True
    )
    print("\nQuestions couvertes avec les scores les plus bas")
    for r in covered[:count]:
        print(f"  {r['hits'][0]['score']:.3f}  {r['id']} [{r['language']}] {r['question']}")
    print("\nQuestions non couvertes avec les scores les plus hauts")
    for r in not_covered[:count]:
        print(
            f"  {r['hits'][0]['score']:.3f}  {r['id']} [{r['language']}] {r['question']}"
            f"  -> {r['hits'][0]['document']}"
        )


def print_misses(results: list[dict]) -> None:
    print(f"\nQuestions couvertes dont le top-{REPORT_K} rate un document attendu")
    missed = [r for r in results if r["answerable"] and not is_in_top_k(r, REPORT_K)]
    if not missed:
        print("  aucune")
    for r in missed:
        got = ", ".join(hit["document"] for hit in r["hits"][:REPORT_K])
        print(f"  {r['id']} [{r['category']}] attendu {r['expected_documents']} / obtenu {got}")


def main() -> None:
    if "--reuse" in sys.argv:
        results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    else:
        questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
        results = run_searches(questions)
        RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRésultats enregistrés dans {RESULTS_FILE}")

    print_hit_table(results)
    print_score_table(results)
    print_threshold_sweep(results)
    print_score_extremes(results)
    print_misses(results)


if __name__ == "__main__":
    main()