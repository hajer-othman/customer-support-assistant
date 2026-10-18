from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.schemas import OrderLookupRequest, OrderStatusOut
from app.tools.orders import get_order_status

app = FastAPI(title="Customer support assistant API")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/orders/lookup", response_model=OrderStatusOut)
def lookup_order(payload: OrderLookupRequest, db: Session = Depends(get_db)):
    order = get_order_status(db, payload.order_number, payload.email)
    if order is None:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    return order