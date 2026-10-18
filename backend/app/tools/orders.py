from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Order, OrderItem, Return, User


def get_order_status(db: Session, order_number: str, email: str) -> dict | None:
    """Renvoie la commande si le numéro ET l'email correspondent, sinon None."""
    # 1. Trouver la commande, uniquement si son propriétaire a cet email
    order = db.execute(
        select(Order)
        .join(User, User.id == Order.user_id)
        .where(Order.order_number == order_number.strip().upper())
        .where(func.lower(User.email) == email.strip().lower())
    ).scalar_one_or_none()

    if order is None:
        return None

    # 2. Les articles de la commande, avec le statut de leur retour s'il existe
    rows = db.execute(
        select(OrderItem, Return.status)
        .outerjoin(Return, Return.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == order.id)
        .order_by(OrderItem.product_name)
    ).all()

    return {
        "order_number": order.order_number,
        "status": order.status,
        "ordered_at": order.ordered_at,
        "delivered_at": order.delivered_at,
        "items": [
            {
                "product_name": item.product_name,
                "size": item.size,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "return_status": return_status,
            }
            for item, return_status in rows
        ],
    }