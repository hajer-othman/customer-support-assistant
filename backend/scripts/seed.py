import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete

from app.db.models import (
    Conversation,
    Message,
    Order,
    OrderItem,
    Return,
    Ticket,
    User,
)
from app.db.session import SessionLocal


def days_ago(n: int, now: datetime) -> datetime:
    return now - timedelta(days=n)


def seed() -> None:
    now = datetime.now(timezone.utc)

    with SessionLocal() as session:
        # 1. Vider les tables de démo, dans l'ordre inverse des dépendances.
        # policy_chunks n'est pas touchée.
        for model in (Ticket, Return, Message, Conversation, OrderItem, Order, User):
            session.execute(delete(model))

        # 2. Utilisateurs
        camille = User(id=uuid.uuid4(), email="camille.martin@example.com",
                       full_name="Camille Martin", role="customer")
        sarah = User(id=uuid.uuid4(), email="sarah.johnson@example.com",
                     full_name="Sarah Johnson", role="customer")
        yassine = User(id=uuid.uuid4(), email="yassine.bensalah@example.com",
                       full_name="Yassine Ben Salah", role="customer")
        lea = User(id=uuid.uuid4(), email="lea.moreau@example.com",
                   full_name="Léa Moreau", role="advisor")
        session.add_all([camille, sarah, yassine, lea])
        session.flush()

        # 3. Commandes et articles. Les dates sont relatives à aujourd'hui.
        # (numéro, client, statut, commandée il y a X jours, livrée il y a X jours, articles)
        orders_data = [
            ("ORD-1001", camille, "delivered", 9, 5, [
                ("Pull en laine", "M", "59.90"),
                ("Jean slim", "40", "69.90"),
                ("T-shirt blanc", "S", "19.90"),
            ]),
            ("ORD-1002", camille, "delivered", 65, 60, [
                ("Baskets blanches", "38", "89.00"),
            ]),
            ("ORD-1003", sarah, "shipped", 3, None, [
                ("Veste imperméable", "L", "119.00"),
            ]),
            ("ORD-1004", sarah, "delivered", 14, 10, [
                ("Robe d'été", "36", "49.90"),
                ("Sneakers", "7", "79.00"),
            ]),
            ("ORD-1005", yassine, "processing", 1, None, [
                ("Chemise", "M", "44.90"),
                ("Ceinture en cuir", "90", "29.90"),
            ]),
            ("ORD-1006", yassine, "cancelled", 12, None, [
                ("Écharpe en laine", "Unique", "35.00"),
            ]),
        ]

        orders = {}
        items = {}  # noms d'articles uniques dans ce jeu de données
        for number, user, status, ordered, delivered, lines in orders_data:
            order = Order(
                id=uuid.uuid4(),
                order_number=number,
                user_id=user.id,
                status=status,
                ordered_at=days_ago(ordered, now),
                delivered_at=days_ago(delivered, now) if delivered is not None else None,
            )
            session.add(order)
            session.flush()
            orders[number] = order
            for name, size, price in lines:
                item = OrderItem(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    product_name=name,
                    size=size,
                    quantity=1,
                    unit_price=Decimal(price),
                )
                session.add(item)
                items[name] = item
        session.flush()

        # 4. Un retour déjà demandé : la robe de Sarah
        session.add(Return(
            id=uuid.uuid4(),
            order_item_id=items["Robe d'été"].id,
            status="requested",
            reason="Taille trop grande",
            created_at=days_ago(2, now),
            updated_at=days_ago(2, now),
        ))

        # 5. Une conversation et un ticket de remboursement déjà ouvert
        conversation = Conversation(
            id=uuid.uuid4(),
            user_id=yassine.id,
            language="fr",
            created_at=days_ago(7, now),
        )
        session.add(conversation)
        session.flush()

        session.add_all([
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                sender="customer",
                content="Bonjour, j'ai annulé la commande ORD-1006 mais je n'ai pas été remboursé.",
                created_at=days_ago(7, now),
            ),
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                sender="assistant",
                content="Je ne peux pas traiter les remboursements moi-même. "
                        "Je transmets votre demande à un conseiller, qui reviendra vers vous.",
                created_at=days_ago(7, now) + timedelta(seconds=30),
            ),
        ])
        session.add(Ticket(
            id=uuid.uuid4(),
            user_id=yassine.id,
            order_id=orders["ORD-1006"].id,
            conversation_id=conversation.id,
            category="refund",
            priority="normal",
            status="open",
            summary="Le client a annulé la commande ORD-1006 et demande le remboursement de l'écharpe.",
            created_at=days_ago(7, now),
            updated_at=days_ago(7, now),
        ))

        session.commit()
        print("Données de test chargées : 4 utilisateurs, 6 commandes, 10 articles, "
              "1 retour, 1 conversation, 2 messages, 1 ticket.")


if __name__ == "__main__":
    seed()