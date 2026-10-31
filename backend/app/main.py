import logging

from app.rag.display import clean_answer

import httpx
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.language import UNSUPPORTED_LANGUAGE_MESSAGE, resolve_language
from app.rag.answering import answer_question
from app.schemas import (
    ChatRequest,
    ChatResponse,
    OrderLookupRequest,
    OrderStatusOut,
    SourceOut,
)
from app.tools.orders import get_order_status

logger = logging.getLogger(__name__)

app = FastAPI(title="Customer support assistant API")

UNAVAILABLE_MESSAGE = (
    "Service temporairement indisponible, réessayez dans un instant. "
    "/ Service temporarily unavailable, please try again shortly."
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message vide")

    language = resolve_language(message, payload.ui_language)
    if language is None:  # langue non prise en charge : message fixe, aucun appel au LLM
        return ChatResponse(
            answer=UNSUPPORTED_LANGUAGE_MESSAGE,
            covered=False,
            language=None,
            sources=[],
        )

    try:
        result = answer_question(db, message, language)
    except (RuntimeError, httpx.HTTPError):
        # le contenu du message du client n'est volontairement pas écrit dans les logs
        logger.exception("Échec de la génération de réponse (langue : %s)", language)
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE)

    return ChatResponse(
        answer=clean_answer(result.text, result.retrieved),
        covered=result.covered,
        language=language,
        sources=[
            SourceOut(document_name=hit.document_name, section_title=hit.section_title)
            for hit in result.sources
        ],
    )


@app.post("/orders/lookup", response_model=OrderStatusOut)
def lookup_order(payload: OrderLookupRequest, db: Session = Depends(get_db)):
    order = get_order_status(db, payload.order_number, payload.email)
    if order is None:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    return order