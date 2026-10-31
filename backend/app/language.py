"""Détection de la langue d'un message de client.

La langue est détectée par le code, jamais par le LLM. Seuls le français et l'anglais
sont pris en charge ; les autres langues reçoivent un message fixe.
"""

from lingua import Language, LanguageDetectorBuilder

SUPPORTED = {"fr", "en"}
DEFAULT_LANGUAGE = "fr"
MIN_CONFIDENCE = 0.7  # en dessous, on ne se fie pas à la détection (messages courts, ambigus)

UNSUPPORTED_LANGUAGE_MESSAGE = (
    "Je peux répondre uniquement en français ou en anglais. "
    "I can only answer in French or English."
)

# On liste aussi quelques langues non prises en charge : sans elles, un message en espagnol
# serait forcément classé « français » ou « anglais » et jamais refusé.
_CODES = {
    Language.FRENCH: "fr",
    Language.ENGLISH: "en",
    Language.SPANISH: "es",
    Language.GERMAN: "de",
    Language.ITALIAN: "it",
    Language.PORTUGUESE: "pt",
    Language.ARABIC: "ar",
}

_DETECTOR = LanguageDetectorBuilder.from_languages(*_CODES).build()


def detect_language(text: str) -> tuple[str | None, float]:
    """Renvoie (code de langue, confiance entre 0 et 1), ou (None, 0.0) si rien n'est détecté."""
    values = _DETECTOR.compute_language_confidence_values(text)
    if not values:
        return None, 0.0
    best = values[0]  # la liste est triée, la plus probable en premier
    return _CODES[best.language], best.value


def resolve_language(message: str, ui_language: str | None = None) -> str | None:
    """Langue de la réponse : "fr", "en", ou None si le message est dans une langue non prise en charge."""
    code, confidence = detect_language(message)
    if code is None or confidence < MIN_CONFIDENCE:
        # détection peu fiable : on prend la langue de l'interface, ou le français par défaut
        return ui_language if ui_language in SUPPORTED else DEFAULT_LANGUAGE
    return code if code in SUPPORTED else None