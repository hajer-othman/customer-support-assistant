import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('customer', 'advisor')", name="ck_users_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True)
    full_name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'shipped', 'delivered', 'cancelled')",
            name="ck_orders_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    product_name: Mapped[str] = mapped_column(String)
    size: Mapped[str] = mapped_column(String)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class Return(Base):
    __tablename__ = "returns"
    __table_args__ = (
        CheckConstraint(
            "status IN ('requested', 'approved', 'refused')",
            name="ck_returns_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # unique=True : un seul retour possible par article
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("order_items.id"), unique=True
    )
    status: Mapped[str] = mapped_column(String, server_default="requested")
    reason: Mapped[str] = mapped_column(Text)
    advisor_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("language IN ('fr', 'en')", name="ck_conversations_language"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    language: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("sender IN ('customer', 'assistant')", name="ck_messages_sender"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"))
    sender: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "category IN ('refund', 'exchange', 'cancellation', "
            "'address_change', 'payment', 'other')",
            name="ck_tickets_category",
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high')", name="ck_tickets_priority"
        ),
        CheckConstraint("status IN ('open', 'resolved')", name="ck_tickets_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"))
    category: Mapped[str] = mapped_column(String)
    priority: Mapped[str] = mapped_column(String, server_default="normal")
    status: Mapped[str] = mapped_column(String, server_default="open")
    summary: Mapped[str] = mapped_column(Text)
    advisor_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"
    __table_args__ = (
        CheckConstraint("language IN ('fr', 'en')", name="ck_policy_chunks_language"),
        # une section par document et par langue : l'ingestion peut être relancée sans doublon
        UniqueConstraint(
            "document_name", "language", "section_title", name="uq_policy_chunks_section"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_name: Mapped[str] = mapped_column(String)
    language: Mapped[str] = mapped_column(String)
    section_title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    # empreinte du texte vectorisé (en-tête + contenu) : détecte les sections modifiées
    content_hash: Mapped[str] = mapped_column(String)
    # mistral-embed renvoie des vecteurs de 1 024 nombres
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))