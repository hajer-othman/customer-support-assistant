from app.language import detect_language, resolve_language

TESTS = [
    ("Quel est le délai pour retourner un article ?", "en"),
    ("What is the return deadline?", "fr"),
    ("ok", "en"),
    ("retour ?", "en"),
    ("¿Cuál es el plazo de devolución?", "fr"),
    ("Wie lange habe ich Zeit für eine Rücksendung?", "fr"),
    ("ما هي مدة الإرجاع؟", "fr"),
    ("12345", "fr"),
]

for message, ui in TESTS:
    code, confidence = detect_language(message)
    result = resolve_language(message, ui)
    print(f"{message!r:50} ui={ui}  détecté={code} ({confidence:.2f})  ->  {result}")